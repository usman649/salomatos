from django.urls import include, path

urlpatterns = [
    path(
        "v1/clinic/",
        include(
            ("apps.clinic.api.v1.urls", "clinic"),
            namespace="clinic",
        ),
    ),
]
