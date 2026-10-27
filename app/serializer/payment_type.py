from rest_framework import serializers
from app.models import PaymentType


class PaymentTypesSerializer(serializers.ModelSerializer):
    class Meta:
        model=PaymentType
        fields='__all__'