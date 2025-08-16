from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.response import Response
from rest_framework import status
from django.utils.crypto import get_random_string
from django.db import transaction
from .models import Receipt, Job
from .serializers import ReceiptSerializer, JobSerializer
from .tasks import process_receipt_job
class HealthView(APIView):
    def get(self, request): return Response({"status":"ok"})
class ParseReceiptView(APIView):
    def post(self, request):
        image_uri = request.data.get("image_uri")
        if not image_uri: return Response({"detail":"image_uri required"}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"preview": True, "image_uri": image_uri})
class ReceiptViewSet(ReadOnlyModelViewSet):
    queryset = Receipt.objects.all().order_by("-created_at")
    serializer_class = ReceiptSerializer
class JobViewSet(ReadOnlyModelViewSet):
    queryset = Job.objects.all().order_by("-created_at")
    serializer_class = JobSerializer
class IngestReceiptView(APIView):
    def post(self, request):
        image_uri = request.data.get("image_uri")
        idem = request.headers.get("Idempotency-Key") or get_random_string(24)
        if not image_uri: return Response({"detail":"image_uri required"}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            job, created = Job.objects.get_or_create(idempotency_key=idem)
            if not created: return Response(JobSerializer(job).data, status=status.HTTP_200_OK)
            process_receipt_job.delay(job.id, image_uri)
            return Response(JobSerializer(job).data, status=status.HTTP_202_ACCEPTED)
