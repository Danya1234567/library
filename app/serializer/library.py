from rest_framework import serializers

from app.models import Shift, City, PaymentType, Library, LibraryBook


class LibrariesSerializer(serializers.ModelSerializer):
    book = serializers.SlugRelatedField(
        many=True,
        slug_field='name',
        read_only=True)
    shift = serializers.SlugRelatedField(
        many=True,
        slug_field='name',
        queryset=Shift.objects.all())
    city = serializers.SlugRelatedField(
        slug_field='name',
        queryset=City.objects.all(),
    )
    payment_type = serializers.SlugRelatedField(
        many=True,
        slug_field='name',
        queryset=PaymentType.objects.all()
    )
    class Meta:
        model = Library
        fields = '__all__'

class LibraryBookSerializer(serializers.ModelSerializer):
    book = serializers.SlugRelatedField(slug_field='name', read_only=True)
    library = serializers.SlugRelatedField(slug_field='name', read_only=True)

    class Meta:
        model = LibraryBook
        fields = ['id', 'library', 'book', 'quantity']


class LibraryBookCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LibraryBook
        fields = ['id', 'library', 'book', 'quantity']

    def validate(self, data):
        if LibraryBook.objects.filter(library=data['library'], book=data['book']).exists():
            raise serializers.ValidationError('This book is already listed in this library—use the balance top-up option.')
        return data


class StockAdjustSerializer(serializers.Serializer):
    delta = serializers.IntegerField(help_text='Positive — deposit; negative — withdrawal.')