import django_filters
from apps.clinic.models import Treatment,TreatmentType

class TreatmentFilter(django_filters.FilterSet):
    patient_id = django_filters.NumberFilter(
        field_name='patient',
    )

    class Meta:
        model = Treatment
        fields = ['patient_id']


class TreatmentTypeFilter(django_filters.FilterSet):
    doctor_type_id = django_filters.NumberFilter(
        field_name='doctor_type',
    )
    class Meta:
        model = TreatmentType
        fields = ['doctor_type_id']