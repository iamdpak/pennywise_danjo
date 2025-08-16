from rest_framework import serializers
from .models import Receipt, Merchant, Category, ReceiptItem, Job
class MerchantSerializer(serializers.ModelSerializer):
    class Meta: model = Merchant; fields = ("id","name","abn","address","normalized_name")
class CategorySerializer(serializers.ModelSerializer):
    class Meta: model = Category; fields = ("id","name","parent")
class ReceiptItemSerializer(serializers.ModelSerializer):
    class Meta: model = ReceiptItem; fields = ("id","line_text","quantity","unit_price","amount")
class ReceiptSerializer(serializers.ModelSerializer):
    merchant = MerchantSerializer(); category = CategorySerializer(allow_null=True)
    items = ReceiptItemSerializer(many=True, required=False)
    class Meta:
        model = Receipt
        fields = ("id","uuid","total","currency","purchased_at","merchant","category","image_uri","raw_json","items","created_at","updated_at")
class JobSerializer(serializers.ModelSerializer):
    class Meta: model = Job; fields = ("id","idempotency_key","receipt","status","error","started_at","finished_at","created_at")
