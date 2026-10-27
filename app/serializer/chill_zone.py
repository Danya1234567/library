from rest_framework import serializers

from app import service
from app.models import ChillZone, ChillZoneBookings, PaymentType, ChillZoneOrderItem, ChillZoneOrder, Product
from app.serializer.library import LibrariesSerializer


class ChillZoneSerializer(serializers.ModelSerializer):
    library=LibrariesSerializer(read_only=True)
    class Meta:
        model = ChillZone
        fields='__all__'

class ChillZoneWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChillZone
        fields=['id','name','branch','capacity','is_active','area','price','library','payment_type','free_seats','image_url']
        extra_kwargs = {'free_seats':{'required':False}}

    def validate(self,data):
        capacity=data.get('capacity',getattr(self.instance,'capacity',None))
        free_seats=data.get('free_seats',getattr(self.instance,'free_seats',None))
        if capacity is not None and free_seats is not None and capacity < free_seats:
            raise serializers.ValidationError('The number of available seats cannot exceed the total capacity')
        return data

    def create(self,validated_data):
        validated_data.setdefault('free_seats',validated_data.get('capacity',25))
        return super().create(validated_data)

class ChillZoneBookingSerializer(serializers.ModelSerializer):
    user=serializers.SlugRelatedField(slug_field='phone_number',read_only=True)
    reviewed_by=serializers.SlugRelatedField(slug_field='username',read_only=True)
    chill_zone=ChillZoneSerializer(read_only=True)
    is_active=serializers.BooleanField(read_only=True)
    order_number=serializers.IntegerField(source='id',read_only=True)
    payment_type=serializers.CharField(source='payment.payment_type.name',read_only=True)
    class Meta:
        model=ChillZoneBookings
        fields=['id','order_number','user','chill_zone','seats','total_price','payment_type','status','is_active','reviewed_by','reviewed_at','created_at']

class ChillZoneBookingWriteSerializer(serializers.ModelSerializer):
    payment_type=serializers.PrimaryKeyRelatedField(queryset=PaymentType.objects.filter(is_active=True))
    class Meta:
        model = ChillZoneBookings
        fields=['id','chill_zone','seats','payment_type']

    def validate_seats(self,value):
        if value < 1:
            raise serializers.ValidationError('You must book at least one seat')
        return value

    def validate(self,data):
        zone=data['chill_zone']
        if not zone.is_active:
            raise serializers.ValidationError('This zone is not available right now')
        if data['seats']> zone.free_seats:
            raise serializers.ValidationError({'seats':'Not enough available seats'})
        return data

    def create(self,validated_data):
        return service.create_chill_booking(
            self.context['request'].user,
            validated_data['chill_zone'],
            validated_data['seats'],
            validated_data['payment_type']
        )

class BookingConfirmSerializer(serializers.Serializer):
    identity_confirmed=serializers.BooleanField()


class ChillOrderItemSerializer(serializers.ModelSerializer):
    product = serializers.SlugRelatedField(slug_field='name', read_only=True)
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = ChillZoneOrderItem
        fields = ['id', 'product', 'quantity', 'unit_price', 'subtotal']

    def get_subtotal(self, obj):
        return obj.unit_price * obj.quantity


class ChillOrderSerializer(serializers.ModelSerializer):
    receipt_number = serializers.IntegerField(source='id', read_only=True)
    booking_order_number = serializers.IntegerField(source='booking.id', read_only=True)
    client = serializers.CharField(source='booking.user.phone_number', read_only=True)
    chill_zone = serializers.CharField(source='booking.chill_zone.name', read_only=True)
    cashier = serializers.SlugRelatedField(slug_field='username', read_only=True)
    payment_type = serializers.CharField(source='payment.payment_type.name', read_only=True)
    items = ChillOrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = ChillZoneOrder
        fields = ['id', 'receipt_number', 'booking_order_number', 'client', 'chill_zone', 'cashier',
                  'payment_type', 'items', 'total_price', 'created_at']


class ChillOrderItemInputSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    quantity = serializers.IntegerField(min_value=1)


class ChillOrderCreateSerializer(serializers.Serializer):
    booking = serializers.PrimaryKeyRelatedField(queryset=ChillZoneBookings.objects.all())
    payment_type = serializers.PrimaryKeyRelatedField(queryset=PaymentType.objects.filter(is_active=True))
    items = ChillOrderItemInputSerializer(many=True, allow_empty=False)

    def create(self, validated_data):
        return service.create_chill_order(self.context['request'].user, **validated_data)