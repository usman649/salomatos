from django.urls import include, path

urlpatterns = [
    path(
        "v1/authentication/",
        include(
            ("apps.authentication.api.v1.urls", "authentication"),
            namespace="authentication",
        ),
    ),
]
