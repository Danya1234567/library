from rest_framework import serializers
from app.models import Genre


class GenresSerializer(serializers.ModelSerializer):
    class Meta:
        model=Genre
        fields='__all__'