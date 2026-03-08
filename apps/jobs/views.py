from django.contrib import messages
from django.core.files.base import ContentFile
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DeleteView, DetailView, ListView

from apps.rules.models import Rule

from .models import PrintJob
from .services import validate_and_repair_pdf
from .tasks import process_job_task


class JobListView(ListView):
    model = PrintJob
    template_name = "jobs/job_list.html"
    context_object_name = "jobs"
    paginate_by = 25


class JobDetailView(DetailView):
    model = PrintJob
    template_name = "jobs/job_detail.html"
    context_object_name = "job"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["rulesets"] = Rule.objects.filter(active=True).order_by("name")
        return ctx


class JobUploadView(View):
    template_name = "jobs/job_upload.html"

    @staticmethod
    def _ruleset_context():
        return {
            "rulesets": Rule.objects.filter(active=True).order_by("name")
        }

    def get(self, request):
        return render(request, self.template_name, self._ruleset_context())

    def post(self, request):
        file = request.FILES.get("file")
        ctx = self._ruleset_context()
        if not file:
            messages.error(request, "No file selected.")
            return render(request, self.template_name, ctx, status=400)
        if not file.name.lower().endswith(".pdf"):
            messages.error(request, "Only PDF files are accepted.")
            return render(request, self.template_name, ctx, status=400)

        # Validate and optionally repair the PDF before saving
        repaired_bytes, pdf_warnings = validate_and_repair_pdf(file)
        if repaired_bytes is None:
            # Unrecoverable — show all warnings as errors
            for w in pdf_warnings:
                messages.error(request, w)
            return render(request, self.template_name, ctx, status=400)

        # Capture user-provided job options
        pages_are_unique = request.POST.get("pages_are_unique") == "on"
        # Step-and-repeat jobs cannot be double-sided (same page fills every cell).
        is_double_sided = (
            request.POST.get("is_double_sided") == "on"
        ) and pages_are_unique

        job = PrintJob.objects.create(
            name=file.name,
            is_double_sided=is_double_sided,
            pages_are_unique=pages_are_unique,
        )
        # Save the (possibly repaired) PDF
        job.file.save(file.name, ContentFile(repaired_bytes), save=True)

        # Warn the user about any repairs made
        for w in pdf_warnings:
            messages.warning(request, w)

        # Apply an explicit ruleset if selected
        ruleset_id = request.POST.get("ruleset_id", "").strip()
        if ruleset_id:
            try:
                ruleset = Rule.objects.select_related(
                    "imposition_template", "cutter_program", "routing_preset"
                ).get(pk=int(ruleset_id))
                from apps.rules.engine import _apply

                _apply(ruleset, job)
                job.save(
                    update_fields=[
                        "imposition_template",
                        "cutter_program",
                        "routing_preset",
                    ]
                )
            except (Rule.DoesNotExist, ValueError):
                messages.warning(
                    request,
                    "Selected ruleset not found.",
                )

        process_job_task.delay(str(job.pk))
        messages.success(request, f"Job '{job.name}' submitted successfully.")
        return redirect("jobs:detail", pk=job.pk)


class JobApplyRulesetView(View):
    """Manually apply a ruleset to a job and immediately re-process it."""

    def post(self, request, pk):
        job = get_object_or_404(PrintJob, pk=pk)
        ruleset_id = request.POST.get("ruleset_id", "").strip()

        if not ruleset_id:
            messages.error(request, "No ruleset selected.")
            return redirect("jobs:detail", pk=pk)

        try:
            ruleset = Rule.objects.select_related(
                "imposition_template", "cutter_program", "routing_preset"
            ).get(pk=int(ruleset_id))
        except (Rule.DoesNotExist, ValueError):
            messages.error(request, "Ruleset not found.")
            return redirect("jobs:detail", pk=pk)

        # Apply the ruleset actions directly (bypass condition matching)
        from apps.rules.engine import _apply

        _apply(ruleset, job)
        job.status = PrintJob.Status.PENDING
        job.save(
            update_fields=[
                "imposition_template",
                "cutter_program",
                "routing_preset",
                "status",
            ]
        )
        # Re-process the job immediately
        process_job_task.delay(str(job.pk))
        messages.success(
            request, f"Ruleset '{ruleset.name}' applied — job is being re-processed."
        )
        return redirect("jobs:detail", pk=pk)


class JobDeleteView(DeleteView):
    model = PrintJob
    template_name = "jobs/job_confirm_delete.html"
    success_url = "/jobs/"

    def form_valid(self, form):
        messages.success(self.request, "Job deleted.")
        return super().form_valid(form)


class JobPreviewView(View):
    """Serve the imposed PDF inline for browser preview before sending to printer."""

    def get(self, request, pk):
        from django.http import FileResponse, Http404

        job = get_object_or_404(PrintJob, pk=pk)
        if not job.imposed_file:
            raise Http404("No imposed file available for this job.")
        response = FileResponse(
            job.imposed_file.open("rb"),
            as_attachment=False,
            filename=f"preview_{job.name}",
            content_type="application/pdf",
        )
        return response


class JobDownloadView(View):
    """Serve the imposed PDF for download."""

    def get(self, request, pk):
        from django.http import FileResponse, Http404

        job = get_object_or_404(PrintJob, pk=pk)
        if not job.imposed_file:
            raise Http404("No imposed file available for this job.")
        response = FileResponse(
            job.imposed_file.open("rb"),
            as_attachment=True,
            filename=f"imposed_{job.name}",
        )
        return response


class JobResendView(View):
    """Re-send an already-processed job to the printer."""

    def post(self, request, pk):
        import os
        import tempfile

        from apps.routing.services import send_to_fiery_lpr

        job = get_object_or_404(PrintJob, pk=pk)
        if not job.imposed_file:
            messages.error(request, "No imposed file available to send.")
            return redirect("jobs:detail", pk=pk)
        if not job.routing_preset:
            messages.error(request, "No printer preset is assigned to this job.")
            return redirect("jobs:detail", pk=pk)

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                with job.imposed_file.open("rb") as f:
                    tmp.write(f.read())
                tmp_path = tmp.name

            send_to_fiery_lpr(tmp_path, job.routing_preset)
            job.status = PrintJob.Status.SENT
            job.save(update_fields=["status"])
            messages.success(request, f"Job '{job.name}' re-sent to printer.")
        except Exception as exc:
            messages.error(request, f"Failed to send job: {exc}")
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

        return redirect("jobs:detail", pk=pk)
