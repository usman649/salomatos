import django_filters
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from apps.calendars.models import Appointment

class AppointmentFilter(django_filters.FilterSet):
    date = django_filters.CharFilter(method='filter_by_week_day')

    class Meta:
        model = Appointment
        fields = []

    def filter_by_week_day(self,queryset,name,value):
        today = timezone.now().date()
        if value == 'day':
            return queryset.filter(date=today)
        elif value == 'week':
            start_of_week = today - timedelta(days=today.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            return queryset.filter(date__range=[start_of_week, end_of_week])
        return queryset

