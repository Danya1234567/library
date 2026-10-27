from rest_framework import serializers

from app.models import Book


class BookSerializer(serializers.ModelSerializer):
    author_ids=serializers.PrimaryKeyRelatedField(source='author', many=True, read_only=True)
    genre_ids=serializers.PrimaryKeyRelatedField(source='genre', many=True, read_only=True)
    author=serializers.SlugRelatedField(many=True,slug_field='name', read_only=True)
    genre=serializers.SlugRelatedField(many=True,slug_field='name', read_only=True)
    total_borrows=serializers.IntegerField(source='rented',read_only=True)
    currently_borrowed=serializers.IntegerField(read_only=True)
    available_copies=serializers.IntegerField(read_only=True)
    rented_out=serializers.SerializerMethodField(read_only=True)
    class Meta:
        model=Book
        fields='__all__'

    def get_rented_out(self,obj):
        copies=getattr(obj,'available_copies',None)
        return None if copies is None else copies<1

class BookWriteSerializer(serializers.ModelSerializer):
    rented=serializers.IntegerField(read_only=True)
    class Meta:
        model=Book
        fields=['id', 'name', 'release_date', 'original_language', 'isbn', 'cover', 'pages','rented', 'price', 'rent_price', 'is_allowed', 'image_url', 'author', 'genre',]