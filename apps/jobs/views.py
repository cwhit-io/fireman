from django.contrib import messages
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import DetailView, ListView

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
