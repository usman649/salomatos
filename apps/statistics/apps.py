from django.apps import AppConfig


class StatisticsConfig(AppConfig):
    name = "apps.statistics"

    def ready(self):
        from . import signals
