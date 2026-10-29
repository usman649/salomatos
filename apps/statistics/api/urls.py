from django.urls import include, path

urlpatterns = [
    path(
        "v1/statistics/",
        include(
            ("apps.statistics.api.v1.urls", "statistics"),
            namespace="statistics",
        ),
    ),
]
