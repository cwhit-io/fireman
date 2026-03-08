from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView

from apps.rules.models import Rule

from .models import PrintJob
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
        return render(request, self.template_name)

    def post(self, request):
        file = request.FILES.get("file")
        if not file:
            messages.error(request, "No file selected.")
            return render(request, self.template_name, status=400)
        if not file.name.lower().endswith(".pdf"):
            messages.error(request, "Only PDF files are accepted.")
            return render(request, self.template_name, status=400)

        job = PrintJob.objects.create(
            name=file.name,
            file=file,
        )
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
        job.save(update_fields=["imposition_template", "cutter_program", "routing_preset"])
        messages.success(request, f"Ruleset '{ruleset.name}' applied to job.")
        return redirect("jobs:detail", pk=pk)
