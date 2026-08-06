from django.contrib import admin
from apps.calendars.models import Appointment

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ['id','patient','doctor','date','time','status']
    list_display_links = ['id','patient','doctor','date','time','status']
    search_fields = ['id','patient','doctor','date','time','status']
