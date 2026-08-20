from django.urls import path
from apps.core.api.v1 import views

urlpatterns = [
    path(
        'recipes/',
        views.RecipeCreateListView.as_view(),
        name='recipe-create-list'
    ),
    path(
        'recipes/<int:pk>/',
        views.RecipeDetailUpdateDeleteView.as_view(),
        name='recipe-detail-update-delete'
    ),
    path(
        'telegram/patients/',
        views.TelegramPatientListView.as_view(),
    ),
    path(
        'telegram/recipes/',
        views.TelegramPatientRecipeListView.as_view(),
        name='telegram_patient_recipes'
    ),
    path(
        'telegram/recipes/<int:recipe_id>/pdf/',
        views.TelegramRecipePDFDownloadView.as_view(),
        name='telegram_recipe_pdf'
    ),
    path(
        'telegram/appointments/',
        views.TelegramPatientAppointmentListView.as_view(),
        name='telegram_patient_appointments'
    ),

]