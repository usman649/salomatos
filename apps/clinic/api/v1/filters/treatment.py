import django_filters
from apps.clinic.models import Treatment,TreatmentType
from django.db.models import F

class TreatmentFilter(django_filters.FilterSet):
    patient_id = django_filters.NumberFilter(
        field_name='patient',
    )
    doctor_id = django_filters.NumberFilter(
        field_name='doctor',
    )
    treatment_type_id = django_filters.NumberFilter(
        field_name='treatment_type',
    )
    remaining = django_filters.BooleanFilter(method='filter_remaining')
    status = django_filters.CharFilter(
        field_name='status',
    )

    class Meta:
        model = Treatment
        fields = ['patient_id', 'doctor_id','treatment_type_id','status']

    def filter_remaining(self, queryset, name, value):
        if value is True:
            return queryset.filter(total_paid__lt=F('total_treatment_cost'))
        if value is False:
            return queryset.filter(total_paid=F('total_treatment_cost'))
        return queryset


class TreatmentTypeFilter(django_filters.FilterSet):
    doctor_type_id = django_filters.NumberFilter(
        field_name='doctor_type',
    )
    class Meta:
        model = TreatmentType
        fields = ['doctor_type_id']