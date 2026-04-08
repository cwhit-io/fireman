from django.apps import AppConfig


class QRCodeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.qrcode"
    label = "qrcode_app"
    verbose_name = "QR Code Generator"
