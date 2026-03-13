import io
import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DeleteView, DetailView, ListView

from .models import MailMergeJob
from .services import inspect_artwork_pdf
from .tasks import process_mail_merge_task

logger = logging.getLogger(__name__)

# Default address block anchor values (inches)
_ADDR_X_DEFAULT_IN = None  # card_width - 4.5 in
_ADDR_Y_DEFAULT_IN = 2.5


class MailMergeJobListView(LoginRequiredMixin, ListView):
    model = MailMergeJob
    template_name = "mailmerge/job_list.html"
    context_object_name = "jobs"
    paginate_by = 25

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(owner=self.request.user)
        return qs


class MailMergeJobDetailView(LoginRequiredMixin, DetailView):
    model = MailMergeJob
    template_name = "mailmerge/job_detail.html"
    context_object_name = "job"

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(owner=self.request.user)
        return qs


class MailMergeArtworkInspectView(LoginRequiredMixin, View):
    """HTMX/JSON endpoint: inspect an uploaded artwork PDF and return page info."""

    def post(self, request):
        artwork = request.FILES.get("artwork_file")
        if not artwork:
            return JsonResponse({"error": "No file uploaded."}, status=400)
        if not artwork.name.lower().endswith(".pdf"):
            return JsonResponse({"error": "File must be a PDF."}, status=400)

        data = inspect_artwork_pdf(io.BytesIO(artwork.read()))
        return JsonResponse(data)


class MailMergeJobUploadView(LoginRequiredMixin, View):
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

        # Inspect the artwork to capture page count and dimensions
        artwork.seek(0)
        pdf_info = inspect_artwork_pdf(io.BytesIO(artwork.read()))
        artwork.seek(0)

        page_count = pdf_info.get("page_count", 1)
        pages = pdf_info.get("pages", [])

        # merge_page: which page gets the address (1-based, default 1)
        try:
            merge_page = int(request.POST.get("merge_page", 1))
        except (TypeError, ValueError):
            merge_page = 1
        merge_page = max(1, min(merge_page, max(page_count, 1)))

        # Card dimensions from the chosen merge page
        card_width = None
        card_height = None
        if pages and merge_page <= len(pages):
            p = pages[merge_page - 1]
            card_width = p["width_pt"]
            card_height = p["height_pt"]

        # Address block position (inches)
        def _parse_float(key):
            val = request.POST.get(key, "").strip()
            try:
                return float(val) if val else None
            except ValueError:
                return None

        addr_x_in = _parse_float("addr_x_in")
        addr_y_in = _parse_float("addr_y_in")

        job = MailMergeJob.objects.create(
            name=name or artwork.name,
            artwork_file=artwork,
            csv_file=csv_file,
            artwork_page_count=page_count,
            merge_page=merge_page,
            card_width=card_width,
            card_height=card_height,
            addr_x_in=addr_x_in,
            addr_y_in=addr_y_in,
            owner=request.user if request.user.is_authenticated else None,
        )
        process_mail_merge_task.delay(str(job.pk))
        messages.success(request, "Mail-merge job submitted.")
        return redirect("mailmerge:detail", pk=job.pk)


class MailMergeJobDeleteView(LoginRequiredMixin, DeleteView):
class MailMergeJobEditView(View):
    """Allow editing address block position and re-triggering the merge."""

    template_name = "mailmerge/job_edit.html"

    def get(self, request, pk):
        job = get_object_or_404(MailMergeJob, pk=pk)
        return render(request, self.template_name, {"job": job})

    def post(self, request, pk):
        job = get_object_or_404(MailMergeJob, pk=pk)

        name = request.POST.get("name", "").strip()
        if name:
            job.name = name

        try:
            merge_page = int(request.POST.get("merge_page", job.merge_page))
        except (TypeError, ValueError):
            merge_page = job.merge_page
        job.merge_page = max(1, min(merge_page, max(job.artwork_page_count or 1, 1)))

        def _parse_float(key):
            val = request.POST.get(key, "").strip()
            try:
                return float(val) if val else None
            except ValueError:
                return None

        addr_x_in = _parse_float("addr_x_in")
        addr_y_in = _parse_float("addr_y_in")
        job.addr_x_in = addr_x_in
        job.addr_y_in = addr_y_in

        job.status = MailMergeJob.Status.PENDING
        job.error_message = ""
        job.save()

        process_mail_merge_task.delay(str(job.pk))
        messages.success(request, "Job updated — re-processing started.")
        return redirect("mailmerge:detail", pk=job.pk)


class MailMergeJobArtworkServeView(View):
    """Serve the artwork PDF for a job (used by the edit-page preview canvas)."""

    def get(self, request, pk):
        job = get_object_or_404(MailMergeJob, pk=pk)
        if not job.artwork_file:
            raise Http404("No artwork file.")
        try:
            with job.artwork_file.open("rb") as fh:
                content = fh.read()
        except Exception as exc:
            raise Http404("Artwork file could not be read.") from exc
        response = HttpResponse(content, content_type="application/pdf")
        response["Content-Disposition"] = "inline"
        return response


    model = MailMergeJob
    template_name = "mailmerge/job_confirm_delete.html"
    success_url = "/mailmerge/"

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(owner=self.request.user)
        return qs

    def form_valid(self, form):
        job = self.get_object()
        # Delete associated files before removing the DB record.
        for field_name in ("artwork_file", "csv_file", "output_file",
                           "gangup_file", "address_pdf_file"):
            try:
                f = getattr(job, field_name, None)
                if f and getattr(f, "name", None):
                    f.delete(save=False)
            except Exception:
                pass
        return super().form_valid(form)


class MailMergeJobDownloadView(LoginRequiredMixin, View):
    def get(self, request, pk):
        if request.user.is_staff:
            job = get_object_or_404(MailMergeJob, pk=pk)
        else:
            job = get_object_or_404(MailMergeJob, pk=pk, owner=request.user)
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
def _serve_job_file(job_file_field, fallback_name: str) -> HttpResponse:
    """Read a FileField and return an HttpResponse, raising Http404 on failure."""
    if not job_file_field:
        raise Http404("File not yet available.")
    try:
        with job_file_field.open("rb") as fh:
            content = fh.read()
    except Exception as exc:
        raise Http404("File could not be read.") from exc
    fname = job_file_field.name.split("/")[-1] or fallback_name
    response = HttpResponse(content, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{fname}"'
    return response

class MailMergeJobDownloadGangupView(View):
    def get(self, request, pk):
        job = get_object_or_404(MailMergeJob, pk=pk)
        return _serve_job_file(job.gangup_file, "gangup.pdf")


class MailMergeJobDownloadAddressPdfView(View):
    def get(self, request, pk):
        job = get_object_or_404(MailMergeJob, pk=pk)
        return _serve_job_file(job.address_pdf_file, "addresses.pdf")
