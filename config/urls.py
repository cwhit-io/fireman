"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path

from config.api import api
from core.views import homepage, qr_page, qr_image, upload_logo, api_generate_preview

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
    path("ping/", lambda r: HttpResponse("pong"), name="ping"),
    path("demo/", include("core.urls", namespace="core")),
    path("qr/", qr_page, name="qr_page"),
    path("qr/image/", qr_image, name="qr_image"),
    path("qr/upload-logo/", upload_logo, name="upload_logo"),
    path("api/qr/generate-preview/", api_generate_preview, name="api_generate_preview"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", homepage, name="homepage"),
    path("jobs/", include("apps.jobs.urls", namespace="jobs")),
    path("templates/", include("apps.impose.urls", namespace="impose")),
    path("presets/", include("apps.routing.urls", namespace="routing")),
    path("cutters/", include("apps.cutter.urls", namespace="cutter")),
    path("mailmerge/", include("apps.mailmerge.urls", namespace="mailmerge")),
]

if settings.DEBUG:
    urlpatterns += [
        path("__reload__/", include("django_browser_reload.urls")),
    ]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
