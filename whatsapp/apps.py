from django.apps import AppConfig

class WhatsappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'whatsapp'
    verbose_name = 'WhatsApp Integration'

    def ready(self):
        import whatsapp.signals  # noqa: F401
