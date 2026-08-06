from django.urls import include, path

urlpatterns = [
    path(
        "v1/calendars/",
        include(
            ("apps.calendars.api.v1.urls", "calendars"),
            namespace="calendars",
        ),
    ),
]
