from rest_framework import serializers
from app.models import Author


class AuthorsSerializer(serializers.ModelSerializer):
    total_borrows = serializers.IntegerField(read_only=True)
    currently_borrowed = serializers.IntegerField(read_only=True)
    class Meta:
        model = Author
        fields = '__all__'