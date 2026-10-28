from django.urls import path
from apps.statistics.api.v1 import views

urlpatterns = [
    path(
        'overview/',
        views.StatisticsOverviewView.as_view(),
        name='overview',
    ),
    path(
        'me/',
        views.StatisticsMyOverviewView.as_view(),
        name='me',
    ),
]
