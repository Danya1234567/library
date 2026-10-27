from rest_framework import serializers

from app import service
from app.models import Book, Library, LibraryBook, RentalItem, Rental, BookQueue


def user_short(user):
    return {'id': user.id, 'username': user.username, 'name': user.name, 'surname': user.surname,
            'phone_number': user.phone_number}

class BookMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = ['id','name','isbn','image_url']

class LibraryMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Library
        fields=['id','name','address','branch']

class BookStockSerializer(serializers.ModelSerializer):
    available=serializers.SerializerMethodField()
    rented_out=serializers.SerializerMethodField()
    class Meta:
        model = LibraryBook
        fields=['library','book','available','rented_out','quantity']

    def get_available(self,obj):
        return obj.quantity > 0

    def get_rented_out(self,obj):
        return obj.quantity < 1

class RentalItemSerializer(serializers.ModelSerializer):
    book=BookMiniSerializer(read_only=True)
    is_returned=serializers.BooleanField(read_only=True)
    class Meta:
        model=RentalItem
        fields=['id','book','is_returned','returned_at']

class RentalSerializer(serializers.ModelSerializer):
    user=serializers.SerializerMethodField()
    library=LibraryMiniSerializer(read_only=True)
    items=RentalItemSerializer(many=True,read_only=True)
    status_label=serializers.CharField(source='get_status_display',read_only=True)
    is_overdue=serializers.SerializerMethodField()
    days_overdue=serializers.SerializerMethodField()
    class Meta:
        model = Rental
        fields=['id','user','library','start_date','until','status','status_label','items','is_overdue','days_overdue','created_at']

    def get_user(self,obj):
        return user_short(obj.user)

    def get_days_overdue(self,obj):
        if obj.status != Rental.Status.ACTIVE or obj.until >= service.today():
            return 0
        if not any(i.returned_at is None for i in obj.items.all()):
            return 0
        return (service.today() - obj.until).days

    def get_is_overdue(self,obj):
        return self.get_days_overdue(obj) > 0

class RentalCreateSerializer(serializers.Serializer):
    library=serializers.PrimaryKeyRelatedField(queryset=Library.objects.all())
    start_date=serializers.DateField()
    until=serializers.DateField()
    books=serializers.PrimaryKeyRelatedField(queryset=Book.objects.all(),many=True,allow_empty=False)
    def validate(self,data):
        today = service.today()
        if data['start_date'] <today:
            raise serializers.ValidationError({'start_date':'Start date can not be in the past'})
        if data['until'] < data['start_date']:
            raise serializers.ValidationError({'until':'End date can not be before start date'})
        if (data['until'] - data['start_date']).days > service.MAX_RENT_DAYS:
            raise serializers.ValidationError({'until':f'Maximum rental period is {service.MAX_RENT_DAYS} days'})
        if len({b.id for b in data['books']}) != len(data['books']):
            raise serializers.ValidationError({'books':'Duplicate books in the request'})
        return data

    def create(self,validated_data):
        return service.create_rental(self.context['request'].user,**validated_data)

class ActiveRentalItemSerializer(serializers.ModelSerializer):
    member=serializers.SerializerMethodField()
    book=BookMiniSerializer(read_only=True)
    library=LibraryMiniSerializer(source='rental.library',read_only=True)
    rental_id=serializers.IntegerField(source='rental.id',read_only=True)
    until=serializers.DateField(source='rental.until',read_only=True)
    days_overdue=serializers.SerializerMethodField()

    class Meta:
        model = RentalItem
        fields=['id','book','rental_id','days_overdue','member','library','until']

    def get_member(self,obj):
        return user_short(obj.rental.user)

    def get_days_overdue(self,obj):
        return max((service.today() - obj.rental.until).days,0)

class ReturnRentalSerializer(serializers.Serializer):
    identity_confirmed=serializers.BooleanField()
    condition=serializers.ChoiceField(choices=RentalItem.Condition.choices,default=RentalItem.Condition.GOOD)

class QueueSerializer(serializers.ModelSerializer):
    book=BookMiniSerializer(read_only=True)
    library=LibraryMiniSerializer(read_only=True)
    position=serializers.SerializerMethodField()
    can_request=serializers.SerializerMethodField()

    class Meta:
        model=BookQueue
        fields=['id','book','library','position','can_request','status','notify_me','expires_at','created_at']

    def get_position(self,obj):
        return service.queue_position(obj)

    def get_can_request(self,obj):
        return obj.status == BookQueue.Status.OFFERED

class QueueJoinSerializer(serializers.Serializer):
    book=serializers.PrimaryKeyRelatedField(queryset=Book.objects.all())
    library=serializers.PrimaryKeyRelatedField(queryset=Library.objects.all())

    def create(self, validated_data):
        return service.join_queue(self.context['request'].user,**validated_data)

class QueueNotifySerializer(serializers.Serializer):
    notify_me=serializers.BooleanField()