from rest_framework import serializers
from django.contrib.auth.models import Group
from users.models import User


class UserSerializer(serializers.ModelSerializer):
    groups = serializers.SlugRelatedField(many=True, read_only=True, slug_field='name')
    permissions = serializers.SerializerMethodField()

    def get_permissions(self, obj):
        return sorted(obj.get_all_permissions())
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'phone_number',
            'name', 'surname', 'groups', 'permissions', 'is_staff', 'is_superuser', 'is_active', 'date_joined',
        ]
        read_only_fields = ['is_staff', 'is_superuser', 'date_joined']

class GroupSerializer(serializers.ModelSerializer):
    permissions = serializers.SlugRelatedField(many=True, read_only=True, slug_field='codename')
    class Meta:
        model = Group
        fields = ['id', 'name', 'permissions']