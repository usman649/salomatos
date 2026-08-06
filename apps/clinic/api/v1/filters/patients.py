import django_filters
from django.db.models import Q
from apps.authentication.models import User
from apps.calendars.models import Appointment

class PatientFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(
        field_name='full_name',
        lookup_expr='icontains'
    )

    status = django_filters.ChoiceFilter(
        field_name='patient_appointments__status',
        choices=Appointment.Status.choices,
        distinct=True
    )
    doctor = django_filters.CharFilter(
        field_name='doctor__full_name',
        lookup_expr='icontains'
    )

    treatment_id = django_filters.NumberFilter(
        field_name='patient_treatments__treatment_type',
        distinct=True
    )


    class Meta:
        model = User
        fields = ['search', 'status', 'doctor','treatment_id']
