from django.urls import path
from apps.calendars.api.v1 import views


urlpatterns = [
    path(
        'appointments/',
        views.AppointmentCreateListView.as_view(),
        name='appointments'
    ),
    path(
        'appointments/<int:pk>/',
        views.AppointmentDetailUpdateDeleteView.as_view(),
        name='appointment-detail-update-delete'
    )


]