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

]