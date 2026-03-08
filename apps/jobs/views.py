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
        ctx["rulesets"] = Rule.objects.filter(active=True).order_by("priority", "name")
        return ctx


class JobUploadView(View):
    template_name = "jobs/job_upload.html"

    def get(self, request):
        ctx = {"job_types": PrintJob.JobType.choices}
        return render(request, self.template_name, ctx)

    def post(self, request):
        file = request.FILES.get("file")
        ctx = {"job_types": PrintJob.JobType.choices}
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
        product_type = request.POST.get("product_type", "").strip()
        is_double_sided = request.POST.get("is_double_sided") == "on"
        pages_are_unique = request.POST.get("pages_are_unique") != "off"

        job = PrintJob.objects.create(
            name=file.name,
            product_type=product_type,
            is_double_sided=is_double_sided,
            pages_are_unique=pages_are_unique,
        )
        # Save the (possibly repaired) PDF
        job.file.save(file.name, ContentFile(repaired_bytes), save=True)

        # Warn the user about any repairs made
        for w in pdf_warnings:
            messages.warning(request, w)

        process_job_task.delay(str(job.pk))
        messages.success(request, f"Job '{job.name}' submitted successfully.")
        return redirect("jobs:detail", pk=job.pk)


class JobApplyRulesetView(View):
    """Manually apply a ruleset to a job."""

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
        job.save(
            update_fields=["imposition_template", "cutter_program", "routing_preset"]
        )
        messages.success(request, f"Ruleset '{ruleset.name}' applied to job.")
        return redirect("jobs:detail", pk=pk)


class JobDeleteView(DeleteView):
    model = PrintJob
    template_name = "jobs/job_confirm_delete.html"
    success_url = "/jobs/"

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Job deleted.")
        return super().delete(request, *args, **kwargs)
