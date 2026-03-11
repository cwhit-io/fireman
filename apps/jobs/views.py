import logging
import math

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import DeleteView, DetailView, ListView

from apps.impose.models import ImpositionTemplate, ProductCategory

from .models import PrintJob
from .services import compute_fiery_name, run_preflight_for_job, validate_and_repair_pdf
from .tasks import process_job_task

logger = logging.getLogger(__name__)


class JobListView(ListView):
    model = PrintJob
    template_name = "jobs/job_list.html"
    context_object_name = "jobs"
    paginate_by = 25

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(is_saved=False)
            .select_related(
                "imposition_template__sheet_size",
                "cutter_program",
            )
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["saved_jobs"] = PrintJob.objects.filter(is_saved=True).select_related(
            "imposition_template__sheet_size", "cutter_program"
        )
        return ctx


class JobDetailView(DetailView):
    model = PrintJob
    template_name = "jobs/job_detail.html"
    context_object_name = "job"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["templates"] = ImpositionTemplate.objects.select_related(
            "product_category", "routing_preset"
        ).order_by("name")
        job = self.object
        tmpl = job.imposition_template
        if tmpl:
            per_sheet = (tmpl.columns or 1) * (tmpl.rows or 1)
            ctx["per_sheet"] = per_sheet
            if job.pages_are_unique and job.page_count and per_sheet:
                sheets_needed = math.ceil(job.page_count / per_sheet)
                ctx["sheets_needed"] = sheets_needed
                ctx["sheets_remaining"] = max(sheets_needed - 1, 0)
        ctx["fiery_name"] = compute_fiery_name(job)
        return ctx


class JobUploadView(View):
    template_name = "jobs/job_upload.html"

    @staticmethod
    def _template_context(category_id=None):
        qs = ImpositionTemplate.objects.select_related(
            "product_category", "routing_preset", "cutter_program"
        ).order_by("name")
        if category_id:
            try:
                qs = qs.filter(product_category_id=int(category_id))
            except (ValueError, TypeError):
                pass
        return {
            "templates": qs,
            "product_categories": ProductCategory.objects.order_by("name"),
            "selected_category": str(category_id) if category_id else "",
        }

    def get(self, request):
        category_id = request.GET.get("category", "").strip() or None
        return render(request, self.template_name, self._template_context(category_id))

    def post(self, request):
        file = request.FILES.get("file")
        category_id = request.POST.get("category_id", "").strip() or None
        ctx = self._template_context(category_id)
        if not file:
            messages.error(request, "No file selected.")
            return render(request, self.template_name, ctx, status=400)
        if not file.name.lower().endswith(".pdf"):
            messages.error(request, "Only PDF files are accepted.")
            return render(request, self.template_name, ctx, status=400)

        max_bytes = settings.MAX_PDF_UPLOAD_BYTES
        if file.size > max_bytes:
            max_mb = max_bytes // (1024 * 1024)
            messages.error(
                request, f"File is too large. Maximum allowed size is {max_mb} MB."
            )
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
        # is_double_sided: explicit form field (checked by default for multi-page).
        # Step-and-repeat jobs (pages_are_unique=False) cannot be double-sided.
        is_double_sided = (
            request.POST.get("is_double_sided") == "on" if pages_are_unique else False
        )

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

        # Apply the selected template
        template_id = request.POST.get("template_id", "").strip()
        if not template_id:
            messages.error(request, "Please select a template.")
            job.delete()
            return render(request, self.template_name, ctx, status=400)
        try:
            template = ImpositionTemplate.objects.select_related(
                "cutter_program", "routing_preset"
            ).get(pk=int(template_id))
            job.imposition_template = template
            job.cutter_program = template.cutter_program
            job.routing_preset = template.routing_preset
            job.save(
                update_fields=[
                    "imposition_template",
                    "cutter_program",
                    "routing_preset",
                ]
            )
        except (ImpositionTemplate.DoesNotExist, ValueError):
            messages.error(request, "Selected template not found.")
            job.delete()
            return render(request, self.template_name, ctx, status=400)

        process_job_task.delay(str(job.pk))
        # Run preflight against the template's trim dimensions
        run_preflight_for_job(job, pdf_bytes=repaired_bytes)
        messages.success(request, f"Job '{job.name}' submitted successfully.")
        return redirect("jobs:detail", pk=job.pk)


class JobUploadTemplatesView(View):
    """HTMX endpoint: return filtered template options for the upload form."""

    def get(self, request):
        from django.utils.html import escape

        category_id = request.GET.get("category_id", "").strip() or None
        qs = ImpositionTemplate.objects.select_related("cut_size").order_by("name")
        if category_id:
            try:
                qs = qs.filter(product_category_id=int(category_id))
            except (ValueError, TypeError):
                pass
        html = '<option value="" disabled selected>— Select template —</option>'
        for tmpl in qs:
            if category_id:
                if tmpl.cut_size:
                    label = escape(tmpl.cut_size.label)
                elif tmpl.cut_width and tmpl.cut_height:
                    label = escape(tmpl.cut_size_label)
                else:
                    label = escape(tmpl.name)
            else:
                label = escape(tmpl.name)
            html += f'<option value="{tmpl.pk}">{label}</option>'
        return HttpResponse(html)


class JobApplyTemplateView(View):
    """Manually apply a template to a job and immediately re-process it."""

    def post(self, request, pk):
        job = get_object_or_404(PrintJob, pk=pk)
        template_id = request.POST.get("template_id", "").strip()

        if not template_id:
            messages.error(request, "No template selected.")
            return redirect("jobs:detail", pk=pk)

        try:
            template = ImpositionTemplate.objects.select_related(
                "cutter_program", "routing_preset"
            ).get(pk=int(template_id))
        except (ImpositionTemplate.DoesNotExist, ValueError):
            messages.error(request, "Template not found.")
            return redirect("jobs:detail", pk=pk)

        job.imposition_template = template
        job.cutter_program = template.cutter_program
        job.routing_preset = template.routing_preset
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
        # Re-run preflight with the new template's trim dimensions
        run_preflight_for_job(job)
        messages.success(
            request, f"Template '{template.name}' applied — job is being re-processed."
        )
        return redirect("jobs:detail", pk=pk)


class JobToggleSaveView(View):
    """Toggle the is_saved flag on a print job."""

    def post(self, request, pk):
        job = get_object_or_404(PrintJob, pk=pk)
        job.is_saved = not job.is_saved
        job.save(update_fields=["is_saved"])
        return redirect(request.POST.get("next", "jobs:list"))


class JobRenameView(View):
    """Update the display name of a print job."""

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request, pk):
        job = get_object_or_404(PrintJob, pk=pk)
        new_name = request.POST.get("name", "").strip()
        if new_name:
            job.name = new_name
            job.save(update_fields=["name"])
            messages.success(request, f"Job renamed to '{new_name}'.")
        else:
            messages.error(request, "Name cannot be empty.")
        return redirect("jobs:detail", pk=pk)


class JobDeleteView(DeleteView):
    model = PrintJob
    template_name = "jobs/job_confirm_delete.html"
    success_url = reverse_lazy("jobs:list")

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


class JobSourcePreviewView(View):
    """Serve the original (pre-imposition) PDF inline for preview."""

    def get(self, request, pk):
        from django.http import FileResponse, Http404

        job = get_object_or_404(PrintJob, pk=pk)
        if not job.file:
            raise Http404("No source file available for this job.")
        response = FileResponse(
            job.file.open("rb"),
            as_attachment=False,
            filename=f"source_{job.name}",
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

        # Allow per-send duplex override
        is_double_sided = request.POST.get("is_double_sided") == "1"
        duplex_override = "duplex_long" if is_double_sided else "simplex"

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                with job.imposed_file.open("rb") as f:
                    tmp.write(f.read())
                tmp_path = tmp.name

            job_title = compute_fiery_name(job)
            send_to_fiery_lpr(
                tmp_path,
                job.routing_preset,
                title=job_title,
                duplex_override=duplex_override,
            )
            job.status = PrintJob.Status.SENT
            job.save(update_fields=["status"])
            messages.success(request, f"Job '{job.name}' sent to printer.")
        except Exception as exc:
            messages.error(request, f"Failed to send job: {exc}")
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

        return redirect("jobs:detail", pk=pk)


class JobPreflightAcknowledgeView(View):
    """Mark preflight results as acknowledged (dismisses the modal)."""

    def post(self, request, pk):
        job = get_object_or_404(PrintJob, pk=pk)
        job.preflight_acknowledged = True
        job.save(update_fields=["preflight_acknowledged"])
        return redirect("jobs:detail", pk=pk)


def calc_sheets(request, pk):
    """Calculate sheets needed for gangup (step-and-repeat) jobs based on a user-supplied finished quantity."""
    job = get_object_or_404(PrintJob, pk=pk)

    if request.method != "POST":
        return redirect("jobs:detail", pk=pk)

    try:
        finished_qty = max(1, int(request.POST.get("finished_qty", 1)))
    except (ValueError, TypeError):
        finished_qty = 1

    tmpl = job.imposition_template
    per_sheet = (tmpl.columns or 1) * (tmpl.rows or 1) if tmpl else 1
    sheets_needed = math.ceil(finished_qty / per_sheet) if per_sheet else 1

    ctx = {
        "job": job,
        "finished_qty": finished_qty,
        "sheets_needed": sheets_needed,
        "per_sheet": per_sheet,
        "sheets_remaining": max(sheets_needed - 1, 0),
        "templates": ImpositionTemplate.objects.select_related(
            "product_category", "routing_preset"
        ).order_by("name"),
        "fiery_name": compute_fiery_name(job),
    }
    return render(request, "jobs/job_detail.html", ctx)
