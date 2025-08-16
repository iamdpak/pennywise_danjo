from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import HealthView, ParseReceiptView, IngestReceiptView, ReceiptViewSet, JobViewSet
router = DefaultRouter()
router.register(r"receipts", ReceiptViewSet, basename="receipt")
router.register(r"jobs", JobViewSet, basename="job")
urlpatterns = [
    path("healthz/", HealthView.as_view()),
    path("parse/receipt/", ParseReceiptView.as_view()),
    path("receipts/ingest/", IngestReceiptView.as_view()),
    path("", include(router.urls)),
]
