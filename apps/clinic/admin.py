from django.contrib import admin
from apps.clinic.models import (
    Treatment,
    TreatmentType,
)



@admin.register(TreatmentType)
class TreatmentTypeAdmin(admin.ModelAdmin):
    list_display = ['id','name','price']
    list_display_links = ['name','price']
    search_fields = ['name','price']

@admin.register(Treatment)
class TreatmentAdmin(admin.ModelAdmin):
    list_display = ['id','patient','doctor','treatment_type','start_date']
    list_display_links = ['patient','doctor','treatment_type','start_date']
    search_fields = ['patient','doctor','treatment_type','start_date']




