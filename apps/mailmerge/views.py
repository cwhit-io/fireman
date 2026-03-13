import logging

from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DeleteView, DetailView, ListView

from .models import MailMergeJob
from .tasks import process_mail_merge_task

logger = logging.getLogger(__name__)


class MailMergeJobListView(ListView):
    model = MailMergeJob
    template_name = "mailmerge/job_list.html"
    context_object_name = "jobs"
    paginate_by = 25


class MailMergeJobDetailView(DetailView):
    model = MailMergeJob
    template_name = "mailmerge/job_detail.html"
    context_object_name = "job"


class MailMergeJobUploadView(View):
    template_name = "mailmerge/job_upload.html"

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        artwork = request.FILES.get("artwork_file")
        csv_file = request.FILES.get("csv_file")
        name = request.POST.get("name", "").strip()

        errors = []
        if not artwork:
            errors.append("Artwork PDF is required.")
        elif not artwork.name.lower().endswith(".pdf"):
            errors.append("Artwork file must be a PDF.")
        if not csv_file:
            errors.append("Address CSV file is required.")
        elif not csv_file.name.lower().endswith(".csv"):
            errors.append("Address file must be a CSV.")

        if errors:
            for msg in errors:
                messages.error(request, msg)
            return render(request, self.template_name, status=400)

        job = MailMergeJob.objects.create(
            name=name or artwork.name,
            artwork_file=artwork,
            csv_file=csv_file,
        )
        process_mail_merge_task.delay(str(job.pk))
        messages.success(request, "Mail-merge job submitted.")
        return redirect("mailmerge:detail", pk=job.pk)


class MailMergeJobDeleteView(DeleteView):
    model = MailMergeJob
    template_name = "mailmerge/job_confirm_delete.html"
    success_url = "/mailmerge/"

    def form_valid(self, form):
        job = self.get_object()
        # Delete associated files before removing the DB record.
        for field_name in ("artwork_file", "csv_file", "output_file"):
            try:
                f = getattr(job, field_name, None)
                if f and getattr(f, "name", None):
                    f.delete(save=False)
            except Exception:
                pass
        return super().form_valid(form)


class MailMergeJobDownloadView(View):
    def get(self, request, pk):
        job = get_object_or_404(MailMergeJob, pk=pk)
        if not job.output_file:
            raise Http404("Output file not yet available.")
        try:
            with job.output_file.open("rb") as fh:
                content = fh.read()
        except Exception as exc:
            raise Http404("Output file could not be read.") from exc
        fname = job.output_file.name.split("/")[-1]
        response = HttpResponse(content, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{fname}"'
        return response
