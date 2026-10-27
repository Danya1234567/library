from rest_framework import serializers

from app.models import Penalty, Notification, PaymentType
from app.serializer.rent import BookMiniSerializer


class PenaltySerializer(serializers.ModelSerializer):
    book=BookMiniSerializer(read_only=True)
    days=serializers.SerializerMethodField()
    class Meta:
        model = Penalty
        fields = ['id','book','days','status','start_date','end_date','total_amount','created_at']

    def get_days(self, obj):
        return (obj.end_date - obj.start_date).days

class PenaltyPaySerializer(serializers.Serializer):
    payment_type=serializers.PrimaryKeyRelatedField(queryset=PaymentType.objects.filter(is_active=True))

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id','title','message','is_read','created_at']