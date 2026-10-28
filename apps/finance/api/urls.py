from django.urls import include, path

urlpatterns = [
    path(
        "v1/finance/",
        include(
            ("apps.finance.api.v1.urls", "finance"),
            namespace="finance",
        ),
    ),
]
