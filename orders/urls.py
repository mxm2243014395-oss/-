from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("forecast/", views.forecast, name="forecast"),
    path("api/latest/", views.api_latest, name="api_latest"),
]
