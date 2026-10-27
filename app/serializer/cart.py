from rest_framework import serializers

from app.models import CartItem, Book
from app.serializer.rent import BookMiniSerializer


class CartItemSerializer(serializers.ModelSerializer):
    book=BookMiniSerializer(read_only=True)
    price=serializers.DecimalField(source='book.price',max_digits=10, decimal_places=2,read_only=True)
    subtotal=serializers.SerializerMethodField()
    class Meta:
        model = CartItem
        fields=['id','book','price','subtotal','quantity']

    def get_subtotal(self,obj):
        return obj.book.price*obj.quantity

class CartAddSerializer(serializers.Serializer):
    book=serializers.PrimaryKeyRelatedField(queryset=Book.objects.filter(is_allowed=True))
    quantity=serializers.IntegerField(min_value=1,default=1)

    def create(self,validated_data):
        item,created = CartItem.objects.get_or_create(user=self.context['request'].user,book=validated_data['book'],defaults={'quantity':validated_data['quantity']})
        if not created:
            item.quantity += validated_data['quantity']
            item.save(update_fields=['quantity'])
        return item

class CartQuantitySerializer(serializers.Serializer):
    quantity=serializers.IntegerField(min_value=1)