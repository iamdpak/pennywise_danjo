from django.db import models
class Merchant(models.Model):
    name = models.CharField(max_length=255)
    abn = models.CharField(max_length=32, blank=True, default="")
    address = models.TextField(blank=True, default="")
    normalized_name = models.CharField(max_length=255, blank=True, default="")
    def __str__(self): return self.name
class Category(models.Model):
    name = models.CharField(max_length=120)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL)
    def __str__(self): return self.name
class Receipt(models.Model):
    uuid = models.CharField(max_length=64, unique=True)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=8, default="AUD")
    purchased_at = models.DateTimeField(null=True, blank=True)
    merchant = models.ForeignKey(Merchant, on_delete=models.PROTECT)
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL)
    image_uri = models.TextField()
    raw_json = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
class ReceiptItem(models.Model):
    receipt = models.ForeignKey(Receipt, related_name="items", on_delete=models.CASCADE)
    line_text = models.TextField()
    quantity = models.FloatField(null=True, blank=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
class Job(models.Model):
    PENDING, RUNNING, SUCCEEDED, FAILED = "PENDING","RUNNING","SUCCEEDED","FAILED"
    STATUSES = [(s, s) for s in (PENDING, RUNNING, SUCCEEDED, FAILED)]
    idempotency_key = models.CharField(max_length=128, unique=True)
    receipt = models.ForeignKey(Receipt, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=16, choices=STATUSES, default=PENDING)
    error = models.TextField(blank=True, default="")
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
