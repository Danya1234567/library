from rest_framework import serializers
from app.models import City, Country


class CountryShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = '__all__'

class CitiesSerializer(serializers.ModelSerializer):
    country = CountryShortSerializer(read_only=True)
    class Meta:
        model=City
        fields='__all__'


class CitiesWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ['id', 'name', 'country']