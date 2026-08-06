from django.contrib import admin
from apps.core.models import (
    Recipe,
    Medicine
)

@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ['id','patient','doctor','notes']
    list_display_links = ['id','patient','doctor','notes']
    search_fields = ['patient','doctor','notes']

@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = ['id','recipe','name','dose','type','frequency','duration','meal','minutes']
    list_display_links = ['id','name','dose','type','frequency','duration','meal','minutes']
    search_fields = ['name','dose','type','frequency','duration','meal','minutes']
