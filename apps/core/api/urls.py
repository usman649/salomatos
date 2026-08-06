from django.urls import include, path

urlpatterns = [
    path(
        "v1/core/",
        include(
            ("apps.core.api.v1.urls", "core"),
            namespace="core",
        ),
    ),
]
