from django.apps import AppConfig


class DetectorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'detector'
    verbose_name = 'Video Forgery Detector'

    def ready(self):
        # Ensure user profiles are created automatically when a new user is registered.
        from . import signals  # noqa: F401
