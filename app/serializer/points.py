from rest_framework import serializers

from app import points
from users.models import PointTransaction, UserBadge


class PointTransactionSerializer(serializers.ModelSerializer):
    reason_label = serializers.CharField(source='get_reason_display', read_only=True)

    class Meta:
        model = PointTransaction
        fields = ['id', 'points', 'reason', 'reason_label', 'source_key', 'created_at']


class UserBadgeSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='get_badge_display', read_only=True)
    description = serializers.SerializerMethodField()

    class Meta:
        model = UserBadge
        fields = ['badge', 'name', 'description', 'earned_at']

    def get_description(self, obj):
        return points.BADGE_DESCRIPTIONS[obj.badge]


class BadgeCatalogSerializer(serializers.Serializer):
    badge = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField()
    earned = serializers.BooleanField()
    earned_at = serializers.DateTimeField(allow_null=True)


class PointsSummarySerializer(serializers.Serializer):
    total_points = serializers.IntegerField()
    level = serializers.CharField()
    level_label = serializers.CharField()
    next_level = serializers.CharField(allow_null=True)
    points_to_next_level = serializers.IntegerField()
    badges = UserBadgeSerializer(many=True)