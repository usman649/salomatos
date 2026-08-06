import django_filters
from apps.clinic.models import Treatment

class TreatmentFilter(django_filters.FilterSet):
    patient_id = django_filters.NumberFilter(
        field_name='patient',
    )

    class Meta:
        model = Treatment
        fields = ['patient_id']