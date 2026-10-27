from rest_framework import serializers

from app import service
from app.models import OrderItem, Order, Library, City, PaymentType
from app.serializer.rent import LibraryMiniSerializer, BookMiniSerializer, user_short


class OrderItemSerializer(serializers.ModelSerializer):
    book = BookMiniSerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = ['id', 'book', 'quantity', 'unit_price']


class OrderSerializer(serializers.ModelSerializer):
    user=serializers.SerializerMethodField()
    library=LibraryMiniSerializer(read_only=True)
    items=OrderItemSerializer(many=True,read_only=True)
    status_label=serializers.CharField(source='get_status_display',read_only=True)
    city=serializers.SlugRelatedField(slug_field='name',read_only=True)

    class Meta:
        model = Order
        fields=['id', 'user', 'delivery_type', 'delivery_method', 'library', 'city', 'address','contact_name', 'contact_phone', 'delivery_fee', 'total_price', 'status','status_label', 'items', 'created_at']

    def get_user(self,obj):
        return user_short(obj.user)

class OrderCreateSerializer(serializers.Serializer):
    delivery_type=serializers.ChoiceField(choices=Order.DeliveryType.choices)
    library=serializers.PrimaryKeyRelatedField(queryset=Library.objects.all(),required=False)
    city=serializers.PrimaryKeyRelatedField(queryset=City.objects.all(),required=False)
    address=serializers.CharField(max_length=255,required=False,allow_blank=True,default='')
    contact_name=serializers.CharField(max_length=100)
    contact_phone=serializers.CharField(max_length=20)
    payment_type=serializers.PrimaryKeyRelatedField(queryset=PaymentType.objects.filter(is_active=True))

    def create(self, validated_data):
        return service.create_order(self.context['request'].user,**validated_data)