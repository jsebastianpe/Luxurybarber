from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
<<<<<<< HEAD
    verbose_name = "Barbería"

    def ready(self):
        from . import checks  # noqa: F401
=======
>>>>>>> f94399e302ad2258f63cf5c33021da487e6234ad
