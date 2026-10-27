from rest_framework import serializers

from app.models import Product


class ProductsSerializer(serializers.ModelSerializer):
    category = serializers.SlugRelatedField(many=True, slug_field='name', read_only=True)
    supplier = serializers.SlugRelatedField(many=True, slug_field='name', read_only=True)

    class Meta:
        model = Product
        fields = ['id', 'name', 'category', 'supplier', 'price', 'image_url', 'is_active']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if not (request and request.user.is_superuser):
            data.pop('supplier', None)
        return data


class ProductsWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'category', 'supplier', 'price', 'image_url', 'is_active']