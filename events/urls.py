from django.urls import path

from . import views

app_name = "events"

urlpatterns = [
    path("ingest/", views.EventIngestionView.as_view(), name="ingest"),
]
