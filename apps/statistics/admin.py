from django.contrib import admin

from apps.statistics.models import TreatmentCompletion


@admin.register(TreatmentCompletion)
class TreatmentCompletionAdmin(admin.ModelAdmin):
    list_display = ["id", "treatment", "completed_on"]
    list_display_links = ["id", "treatment"]
    raw_id_fields = ["treatment"]
