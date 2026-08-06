from django.urls import path
from apps.authentication.api.v1 import views

urlpatterns = [
    path(
        'login/',
         views.UserLoginView.as_view(),
         name='login'
    ),
    path(
        'me/',
         views.UserMeView.as_view(),
         name='me'
    ),
    path(
        'update/<int:pk>/',
         views.UserUpdateView.as_view(),
         name='update'
    )


]