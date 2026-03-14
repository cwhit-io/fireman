import io
import json
import logging
import os
import shutil
import tempfile

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

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from .models import DEFAULT_CSV_FIELDS, AddressBlockConfig

        config = AddressBlockConfig.get_solo()
        ctx["addr_config"] = config
        ctx["csv_fields_json"] = json.dumps(config.csv_fields or DEFAULT_CSV_FIELDS)
        return ctx


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

    def _get_context(self):
        from apps.impose.models import ImpositionTemplate

        from .models import DEFAULT_CSV_FIELDS, AddressBlockConfig

        templates = ImpositionTemplate.objects.filter(allow_mailmerge=True).order_by(
            "name"
        )
        config = AddressBlockConfig.get_solo()
        return {
            "impose_templates": templates,
            "addr_config": config,
            "csv_fields_json": json.dumps(config.csv_fields or DEFAULT_CSV_FIELDS),
        }

    def get(self, request):
        return render(request, self.template_name, self._get_context())

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
            ctx = self._get_context()
            return render(request, self.template_name, ctx, status=400)

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

        # Imposition template selection
        impose_template = None
        impose_template_id = request.POST.get("impose_template_id", "").strip()
        if impose_template_id:
            from apps.impose.models import ImpositionTemplate

            try:
                impose_template = ImpositionTemplate.objects.get(
                    pk=int(impose_template_id), allow_mailmerge=True
                )
            except (ImpositionTemplate.DoesNotExist, ValueError, TypeError):
                impose_template = None

        # Optional per-job address position override from form POST
        addr_x_in = None
        addr_y_in = None
        for field in ("addr_x_in", "addr_y_in"):
            val = request.POST.get(field, "").strip()
            if val:
                try:
                    if field == "addr_x_in":
                        addr_x_in = float(val)
                    else:
                        addr_y_in = float(val)
                except (ValueError, TypeError):
                    pass

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
            impose_template=impose_template,
            owner=request.user if request.user.is_authenticated else None,
        )
        process_mail_merge_task.delay(str(job.pk))
        messages.success(request, "Mail-merge job submitted.")
        return redirect("mailmerge:detail", pk=job.pk)


class MailMergeJobDeleteView(LoginRequiredMixin, DeleteView):
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
        for field_name in (
            "artwork_file",
            "csv_file",
            "output_file",
            "gangup_file",
            "address_pdf_file",
        ):
            try:
                f = getattr(job, field_name, None)
                if f and getattr(f, "name", None):
                    f.delete(save=False)
            except Exception:
                pass
        return super().form_valid(form)


class MailMergeJobEditView(View):
    """Edit an existing mail-merge job and re-trigger processing."""

    template_name = "mailmerge/job_edit.html"

    def _get_job(self, pk):
        return get_object_or_404(MailMergeJob, pk=pk)

    def _get_context(self, job):
        from apps.impose.models import ImpositionTemplate

        from .models import DEFAULT_CSV_FIELDS, AddressBlockConfig

        templates = ImpositionTemplate.objects.filter(allow_mailmerge=True).order_by(
            "name"
        )
        config = AddressBlockConfig.get_solo()
        return {
            "job": job,
            "impose_templates": templates,
            "addr_config": config,
            "csv_fields_json": json.dumps(config.csv_fields or DEFAULT_CSV_FIELDS),
        }

    def get(self, request, pk):
        job = self._get_job(pk)
        return render(request, self.template_name, self._get_context(job))

    def post(self, request, pk):
        job = self._get_job(pk)

        name = request.POST.get("name", "").strip()
        if name:
            job.name = name

        # merge_page
        try:
            merge_page = int(request.POST.get("merge_page", job.merge_page))
        except (TypeError, ValueError):
            merge_page = job.merge_page
        job.merge_page = max(1, min(merge_page, max(job.artwork_page_count or 1, 1)))

        # Imposition template
        impose_template_id = request.POST.get("impose_template_id", "").strip()
        if impose_template_id:
            from apps.impose.models import ImpositionTemplate

            try:
                job.impose_template = ImpositionTemplate.objects.get(
                    pk=int(impose_template_id), allow_mailmerge=True
                )
            except (ImpositionTemplate.DoesNotExist, ValueError, TypeError):
                pass
        elif "impose_template_id" in request.POST:
            job.impose_template = None

        # Optional per-job address position override
        for field in ("addr_x_in", "addr_y_in"):
            val = request.POST.get(field, "").strip()
            if val:
                try:
                    setattr(job, field, float(val))
                except (ValueError, TypeError):
                    pass

        job.status = MailMergeJob.Status.PENDING
        job.save()
        process_mail_merge_task.delay(str(job.pk))
        messages.success(request, "Job updated and re-processing started.")
        return redirect("mailmerge:detail", pk=pk)


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


class MailMergeJobDownloadGangupView(View):
    def get(self, request, pk):
        job = get_object_or_404(MailMergeJob, pk=pk)
        return _serve_job_file(job.gangup_file, "gangup.pdf")


class MailMergeJobDownloadAddressPdfView(View):
    def get(self, request, pk):
        job = get_object_or_404(MailMergeJob, pk=pk)
        return _serve_job_file(job.address_pdf_file, "addresses.pdf")


class MailMergeGenerateMergedView(LoginRequiredMixin, View):
    """Trigger on-demand generation of the full merged PDF."""

    def post(self, request, pk):
        if request.user.is_staff:
            job = get_object_or_404(MailMergeJob, pk=pk)
        else:
            job = get_object_or_404(MailMergeJob, pk=pk, owner=request.user)

        if job.status not in (MailMergeJob.Status.DONE, MailMergeJob.Status.ERROR):
            messages.warning(
                request, "Job must be completed before generating merged PDF."
            )
            return redirect("mailmerge:detail", pk=pk)

        from .tasks import generate_merged_pdf_task

        generate_merged_pdf_task.delay(str(job.pk))
        messages.success(request, "Merged PDF generation started.")
        return redirect("mailmerge:detail", pk=pk)


class MailMergeJobSendGangupToFieryView(LoginRequiredMixin, View):
    """Send the artwork gang-up PDF to the Fiery."""

    def post(self, request, pk):
        if request.user.is_staff:
            job = get_object_or_404(MailMergeJob, pk=pk)
        else:
            job = get_object_or_404(MailMergeJob, pk=pk, owner=request.user)

        if not job.gangup_file:
            messages.error(request, "Gang-up PDF not yet available.")
            return redirect("mailmerge:detail", pk=pk)

        preset = None
        if job.impose_template and job.impose_template.routing_preset:
            preset = job.impose_template.routing_preset
        if not preset:
            messages.error(
                request,
                "No printer preset assigned. Set an imposition template with a routing preset.",
            )
            return redirect("mailmerge:detail", pk=pk)

        tmp_path = None
        try:
            from apps.routing.services import send_to_fiery_lpr

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                with job.gangup_file.open("rb") as f:
                    shutil.copyfileobj(f, tmp)
                tmp_path = tmp.name

            title = f"{job.name or str(job.pk)}_master"
            send_to_fiery_lpr(tmp_path, preset, title=title)
            messages.success(request, "Gang-up PDF sent to printer.")
        except Exception as exc:
            messages.error(request, f"Failed to send: {exc}")
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

        return redirect("mailmerge:detail", pk=pk)


class MailMergeJobSendAddressesToFieryView(LoginRequiredMixin, View):
    """Send the address step-and-repeat PDF to the Fiery with blank pages interleaved.

    For two-sided printing the address PDF needs a blank page paired with each
    address sheet so the press feeds correctly:

    * merge_page == 1  (address on front/side 1) → [addr, blank, addr, blank, …]
    * merge_page != 1  (address on back/side 2)  → [blank, addr, blank, addr, …]
    """

    def post(self, request, pk):
        if request.user.is_staff:
            job = get_object_or_404(MailMergeJob, pk=pk)
        else:
            job = get_object_or_404(MailMergeJob, pk=pk, owner=request.user)

        if not job.address_pdf_file:
            messages.error(request, "Address PDF not yet available.")
            return redirect("mailmerge:detail", pk=pk)

        preset = None
        if job.impose_template and job.impose_template.routing_preset:
            preset = job.impose_template.routing_preset
        if not preset:
            messages.error(
                request,
                "No printer preset assigned. Set an imposition template with a routing preset.",
            )
            return redirect("mailmerge:detail", pk=pk)

        tmp_path = None
        try:
            from pypdf import PdfReader, PdfWriter

            from apps.routing.services import send_to_fiery_lpr

            # Build a new PDF with blank pages interleaved for duplex printing.
            with job.address_pdf_file.open("rb") as f:
                reader = PdfReader(f)
                writer = PdfWriter()
                for page in reader.pages:
                    mb = page.mediabox
                    w, h = float(mb.width), float(mb.height)
                    if job.merge_page == 1:
                        # Address on front — blank goes on the back
                        writer.add_page(page)
                        writer.add_blank_page(width=w, height=h)
                    else:
                        # Address on back — blank goes on the front
                        writer.add_blank_page(width=w, height=h)
                        writer.add_page(page)

                import io as _io

                buf = _io.BytesIO()
                writer.write(buf)
                address_bytes = buf.getvalue()

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(address_bytes)
                tmp_path = tmp.name

            title = f"{job.name or str(job.pk)}_addresses"
            send_to_fiery_lpr(tmp_path, preset, title=title)
            messages.success(request, "Address PDF sent to printer.")
        except Exception as exc:
            messages.error(request, f"Failed to send: {exc}")
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

        return redirect("mailmerge:detail", pk=pk)


class MailMergeJobRecordsView(LoginRequiredMixin, View):
    """JSON endpoint: return parsed CSV records for client-side record preview."""

    def get(self, request, pk):
        if request.user.is_staff:
            job = get_object_or_404(MailMergeJob, pk=pk)
        else:
            job = get_object_or_404(MailMergeJob, pk=pk, owner=request.user)

        if not job.csv_file:
            return JsonResponse({"records": []})

        from .services import parse_usps_csv

        try:
            with job.csv_file.open("rb") as fh:
                records = parse_usps_csv(fh)
        except Exception:
            return JsonResponse({"records": []})

        return JsonResponse({"records": records})
