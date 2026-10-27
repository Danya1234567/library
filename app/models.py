import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models as m
from django.db.models import F, Q
from django.utils import timezone

from users.models import User

class Country(m.Model):
    name=m.CharField(max_length=100,unique=True)
    iso_country=m.CharField(max_length=5)
    def __str__(self):
        return self.name

class Category(m.Model):
    name = m.CharField(max_length=100)
    def __str__(self):
        return self.name

class City(m.Model):
    name=m.CharField(max_length=100)
    country=m.ForeignKey(Country,on_delete=m.CASCADE)
    def __str__(self):
        return self.name

class Publisher(m.Model):
    name=m.CharField(max_length=100)
    def __str__(self):
        return self.name

class Shift(m.Model):
    name=m.CharField(max_length=100)
    start_shift=m.TimeField()
    end_shift=m.TimeField()
    is_working_on_weekend=m.BooleanField(default=True)
    def __str__(self):
        return self.name

class Supplier(m.Model):
    name=m.CharField(max_length=100)
    about=m.TextField()
    phone=m.CharField(max_length=20)
    email=m.EmailField(blank=True,null=True)

    def __str__(self):
        return self.name

class Position(m.Model):
    name=m.CharField(max_length=100)
    def __str__(self):
        return self.name

class PaymentType(m.Model):
    name=m.CharField(max_length=100)
    is_active=m.BooleanField(default=True)
    def __str__(self):
        return self.name

class Genre(m.Model):
    name=m.CharField(max_length=100)
    def __str__(self):
        return self.name

class Author(m.Model):
    name=m.CharField(max_length=100)
    about=m.TextField()
    sex=(('Female','Female'),('Male','Male'))
    sex=m.CharField(choices=sex,default='Female',max_length=10)
    country=m.CharField(max_length=50)
    date_of_birth=m.DateField(null=True,blank=True)
    date_of_death=m.DateField(null=True,blank=True)
    image_url = m.URLField(max_length=500, null=True, blank=True)
    def __str__(self):
        return self.name

class Book(m.Model):
    cover=(('Hard cover','Hard cover'),('Paperback cover','Paperback cover'))
    name=m.CharField(max_length=100)
    release_date=m.DateField()
    original_language=m.CharField(max_length=100)
    isbn=m.CharField(max_length=20)
    cover=m.CharField(choices=cover,default='Hard cover',max_length=50)
    pages=m.PositiveIntegerField()
    rented=m.PositiveIntegerField(default=0)
    rent_price=m.DecimalField(max_digits=10,decimal_places=2,help_text='Rental price per day ^_^')
    price=m.DecimalField(max_digits=10,decimal_places=2)
    is_allowed=m.BooleanField(default=True)
    image_url = m.URLField(max_length=500, null=True, blank=True)
    author=m.ManyToManyField(Author,related_name='books')
    genre=m.ManyToManyField(Genre,related_name='books')
    def __str__(self):
        return self.name

class Library(m.Model):
    name = m.CharField(max_length=100)
    address = m.CharField(max_length=100)
    area = m.SmallIntegerField()
    branch = m.CharField(max_length=10)
    book = m.ManyToManyField(Book, through='LibraryBook', related_name='book')
    city = m.ForeignKey(City, on_delete=m.CASCADE)
    shift = m.ManyToManyField(Shift, related_name='shift')
    payment_type = m.ManyToManyField(PaymentType, related_name='payment_type')
    def __str__(self):
        return self.name

class LibraryBook(m.Model):
    library = m.ForeignKey(Library, on_delete=m.CASCADE, related_name='library_books')
    book = m.ForeignKey(Book, on_delete=m.CASCADE, related_name='library_books')
    quantity = m.PositiveIntegerField(default=0)
    class Meta:
        unique_together = ('library', 'book')
    def __str__(self):
        return f'{self.book} - {self.library} ({self.quantity} шт.)'

class Payment(m.Model):
    price=m.DecimalField(max_digits=10,decimal_places=2)
    is_success=m.BooleanField(default=False)
    payment_type=m.ForeignKey(PaymentType,on_delete=m.PROTECT)
    def __str__(self):
        return str(self.price)

class ChillZone(m.Model):
    name = m.CharField(max_length=100)
    branch = m.CharField(max_length=10)
    capacity = m.PositiveIntegerField(default=25)
    free_seats = m.PositiveIntegerField(default=0)
    is_active = m.BooleanField(default=True)
    area = m.SmallIntegerField()
    image_url = m.URLField(max_length=500, null=True, blank=True)
    price = m.DecimalField(max_digits=10, decimal_places=2,validators=[MinValueValidator(Decimal('0'))],help_text='price per 1 seats',)
    payment_type = m.ForeignKey(PaymentType, on_delete=m.PROTECT)
    library = m.ForeignKey(Library, on_delete=m.CASCADE, related_name='chill_zones')

    class Meta:
        constraints = [m.CheckConstraint(condition=Q(free_seats__lte=F('capacity')),name='chillzone_free_seats_lte_capacity',),]
    def __str__(self):
        return f'{self.name} ({self.branch})'


class ChillZoneBookings(m.Model):
    class Status(m.TextChoices):
        PENDING = 'pending', 'Pending'
        CONFIRMED = 'confirmed', 'Confirmed'
        REJECTED = 'rejected', 'Rejected'
        CANCELLED = 'cancelled', 'Cancelled'
    user = m.ForeignKey(settings.AUTH_USER_MODEL, on_delete=m.CASCADE,related_name='chill_zone_bookings')
    chill_zone = m.ForeignKey(ChillZone, on_delete=m.CASCADE, related_name='bookings')
    seats = m.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    payment = m.OneToOneField(Payment, on_delete=m.PROTECT, null=True, blank=True,related_name='chill_zone_booking')
    total_price = m.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = m.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    reviewed_by = m.ForeignKey(settings.AUTH_USER_MODEL, on_delete=m.SET_NULL,null=True, blank=True, related_name='reviewed_chill_zone_bookings')
    reviewed_at = m.DateTimeField(null=True, blank=True)
    created_at = m.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        permissions = [('review_chillzonebookings', 'Can confirm or reject chill zone bookings'),]

    @property
    def is_active(self):
        return self.status in (self.Status.PENDING, self.Status.CONFIRMED)

    def __str__(self):
        return f'{self.user} - {self.chill_zone} ({self.seats})'

class Product(m.Model):
    name=m.CharField(max_length=100)
    price=m.DecimalField(max_digits=10,decimal_places=2)
    date_of_expiry=m.DateField()
    quantity=m.PositiveIntegerField(default=0)
    image_url = m.URLField(max_length=500, null=True, blank=True)
    category=m.ManyToManyField(Category,related_name='category')
    supplier=m.ManyToManyField(Supplier,related_name='suppliers')
    def __str__(self):
        return self.name

class ProductCategory(m.Model):
    name = m.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Subscription(m.Model):
    status=(('Active','Active'),('Expired','Expired'),('Cancelled','Cancelled'))
    user=m.ForeignKey(User, on_delete=m.CASCADE)
    price=m.DecimalField(max_digits=10,decimal_places=2)
    status=m.CharField(choices=status,max_length=50,default='Active')
    start_date=m.DateField()
    end_date=m.DateField()
    books_limit=m.PositiveIntegerField(default=5)
    payment=m.OneToOneField(Payment, on_delete=m.CASCADE)
    created_at = m.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user}'

class Rental(m.Model):
    class Status(m.TextChoices):
        SENT = 'sent', 'Sent'
        PREPARING = 'preparing', 'Preparing'
        READY = 'ready', 'Ready for pick up'
        ACTIVE = 'active', 'Active'
        COMPLETED = 'completed', 'Completed'
        REJECTED = 'rejected', 'Rejected'
        CANCELLED = 'cancelled', 'Cancelled'
    user = m.ForeignKey(User, on_delete=m.CASCADE, related_name='rentals')
    subscription = m.ForeignKey(Subscription, on_delete=m.PROTECT, related_name='rentals')
    library = m.ForeignKey(Library, on_delete=m.PROTECT, related_name='rentals',help_text='Pickup and return location')
    start_date = m.DateField()
    until = m.DateField()
    status = m.CharField(max_length=20, choices=Status.choices, default=Status.SENT)
    processed_by = m.ForeignKey(User, on_delete=m.SET_NULL, null=True, blank=True,related_name='processed_rentals')
    created_at = m.DateTimeField(auto_now_add=True)
    updated_at = m.DateTimeField(auto_now=True)
    books = m.ManyToManyField(Book, through='RentalItem', related_name='rentals')
    class Meta:
        ordering = ['-created_at']
        constraints = [m.CheckConstraint(condition=Q(until__gte=F('start_date')), name='rental_until_gte_start'),]
        permissions = [('manage_rentals', 'Can process rental requests, hand over and register returns'),]

    def __str__(self):
        return f'Rental #{self.pk} {self.user} ({self.status})'


class RentalItem(m.Model):
    class Condition(m.TextChoices):
        GOOD = 'good', 'Хорошее'
        DAMAGED = 'damaged', 'Повреждено'
        LOST = 'lost', 'Утеряно'
    rental = m.ForeignKey(Rental,on_delete=m.CASCADE,related_name='items')
    book = m.ForeignKey(Book,on_delete=m.CASCADE,related_name='rental_items')
    returned_at = m.DateField(null=True, blank=True)
    returned_by = m.ForeignKey(User,on_delete=m.SET_NULL,null=True,blank=True,related_name='registered_returns')
    condition = m.CharField(max_length=20,choices=Condition.choices,default=Condition.GOOD)
    class Meta:
        unique_together = ('rental', 'book')
    @property
    def is_returned(self):
        return self.returned_at is not None
    def __str__(self):
        return f'{self.rental_id} - {self.book}'

class BookQueue(m.Model):
    class Status(m.TextChoices):
        WAITING = 'waiting', 'Waiting'
        OFFERED = 'offered', 'Offered'
        FULFILLED = 'fulfilled', 'Fulfilled'
        EXPIRED = 'expired', 'Expired'
        LEFT = 'left', 'Left'
    user = m.ForeignKey(User, on_delete=m.CASCADE, related_name='queue_entries')
    book = m.ForeignKey(Book, on_delete=m.CASCADE, related_name='queue_entries')
    library = m.ForeignKey(Library, on_delete=m.CASCADE, related_name='queue_entries')
    status = m.CharField(max_length=20, choices=Status.choices, default=Status.WAITING)
    notify_me = m.BooleanField(default=True)
    created_at = m.DateTimeField(auto_now_add=True)
    offered_at = m.DateTimeField(null=True, blank=True)
    expires_at = m.DateTimeField(null=True, blank=True)
    class Meta:
        ordering = ['created_at']
        constraints = [m.UniqueConstraint(fields=['user', 'book', 'library'],condition=Q(status__in=['waiting', 'offered']),name='one_active_queue_entry',),]

class Penalty(m.Model):
    class Status(m.TextChoices):
        PAID = 'Paid', 'Paid'
        UNPAID = 'Unpaid', 'Unpaid'
    user = m.ForeignKey(User, on_delete=m.CASCADE, related_name='penalties')
    book = m.ForeignKey(Book, on_delete=m.CASCADE)
    rental_item = m.ForeignKey(RentalItem, on_delete=m.CASCADE, null=True, blank=True,related_name='penalties')
    status = m.CharField(max_length=50, choices=Status.choices, default=Status.UNPAID)
    start_date = m.DateField()
    end_date = m.DateField()
    total_amount = m.DecimalField(max_digits=10, decimal_places=2)
    payment = m.OneToOneField(Payment, on_delete=m.SET_NULL, null=True, blank=True)
    created_at = m.DateTimeField(auto_now_add=True)

class Notification(m.Model):
    user = m.ForeignKey(User, on_delete=m.CASCADE, related_name='notifications')
    title = m.CharField(max_length=150)
    message = m.TextField(blank=True)
    is_read = m.BooleanField(default=False)
    created_at = m.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-created_at']

class Wishlist(m.Model):
    user=m.ForeignKey(User, on_delete=m.CASCADE)
    book=m.ForeignKey(Book, on_delete=m.CASCADE)
    created_at=m.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f'{self.user} - {self.book}'

class CartItem(m.Model):
    user = m.ForeignKey(User, on_delete=m.CASCADE, related_name='cart_items')
    book = m.ForeignKey(Book, on_delete=m.CASCADE)
    quantity = m.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    created_at = m.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = ('user', 'book')

class Order(m.Model):
    class DeliveryType(m.TextChoices):
        PICKUP = 'pickup', 'Pick up from branch'
        DELIVERY = 'delivery', 'Home delivery'
    class DeliveryMethod(m.TextChoices):
        BRANCH = 'branch', 'From the nearest branch'
        POST = 'post', 'By post'
    class Status(m.TextChoices):
        SENT = 'sent', 'Sent'
        PREPARING = 'preparing', 'Preparing'
        READY = 'ready', 'Ready for pick up'
        COMPLETED = 'completed', 'Completed'
        ON_THE_WAY = 'on_the_way', 'On the way'
        DELIVERED = 'delivered', 'Delivered'
    user = m.ForeignKey(User, on_delete=m.CASCADE, related_name='orders')
    delivery_type = m.CharField(max_length=20, choices=DeliveryType.choices)
    delivery_method = m.CharField(max_length=20, choices=DeliveryMethod.choices, null=True, blank=True)
    library = m.ForeignKey(Library, on_delete=m.PROTECT, related_name='orders',help_text='A branch for order pickup or a branch from which deliveries are dispatched')
    city = m.ForeignKey(City, on_delete=m.PROTECT, null=True, blank=True)
    address = m.CharField(max_length=255, blank=True)
    contact_name = m.CharField(max_length=100)
    contact_phone = m.CharField(max_length=20)
    delivery_fee = m.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_price = m.DecimalField(max_digits=10, decimal_places=2)
    payment = m.OneToOneField(Payment, on_delete=m.PROTECT)
    status = m.CharField(max_length=20, choices=Status.choices, default=Status.SENT)
    processed_by = m.ForeignKey(User, on_delete=m.SET_NULL, null=True, blank=True,related_name='processed_orders')
    courier = m.ForeignKey(User, on_delete=m.SET_NULL, null=True, blank=True,related_name='delivered_orders')
    created_at = m.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-created_at']
        permissions = [
            ('manage_orders', 'Can process pick-up orders (accept, prepare, hand over)'),
            ('deliver_orders', 'Can accept and deliver home-delivery orders'),]

class OrderItem(m.Model):
    order = m.ForeignKey(Order, on_delete=m.CASCADE, related_name='items')
    book = m.ForeignKey(Book, on_delete=m.PROTECT)
    quantity = m.PositiveIntegerField(default=1)
    unit_price = m.DecimalField(max_digits=10, decimal_places=2)


class ChillZoneOrder(m.Model):
    booking = m.ForeignKey(ChillZoneBookings, on_delete=m.PROTECT, related_name='product_orders',help_text='Подтверждённая бронь клиента (первый чек)')
    cashier = m.ForeignKey(User, on_delete=m.SET_NULL, null=True, related_name='cash_register_orders')
    payment = m.OneToOneField(Payment, on_delete=m.PROTECT, related_name='chill_zone_order')
    total_price = m.DecimalField(max_digits=10, decimal_places=2)
    created_at = m.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        permissions = [('use_cash_register', 'Can use the chill zone cash register (see products, sell, print receipts)'),]

class ChillZoneOrderItem(m.Model):
    order = m.ForeignKey(ChillZoneOrder, on_delete=m.CASCADE, related_name='items')
    product = m.ForeignKey(Product, on_delete=m.PROTECT)
    quantity = m.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = m.DecimalField(max_digits=10, decimal_places=2)


class ShelfItem(m.Model):
    class Status(m.TextChoices):
        TO_READ = 'to_read', 'To read'
        CURRENTLY_READING = 'currently_reading', 'Currently reading'
        READ = 'read', 'Read'
    user = m.ForeignKey(User, on_delete=m.CASCADE, related_name='shelf_items')
    book = m.ForeignKey(Book, on_delete=m.CASCADE, related_name='shelf_items')
    status = m.CharField(max_length=20, choices=Status.choices)
    added_at = m.DateTimeField(default=timezone.now,help_text='Когда книга попала в текущий список (при переносе обновляется)')
    finished_at = m.DateField(null=True, blank=True, help_text='Дата завершения чтения, только для списка Read')
    show_in_profile = m.BooleanField(default=False, help_text="Hozir o'qiyapti: показывать в профиле (до 4 книг)")

    class Meta:
        ordering = ['-added_at']
        constraints = [
            m.UniqueConstraint(fields=['user', 'book'], name='one_shelf_entry_per_book'),
            m.CheckConstraint(condition=Q(status='read') | Q(finished_at__isnull=True),
                              name='shelf_finish_date_only_for_read'),
            m.CheckConstraint(condition=~Q(status='read') | Q(finished_at__isnull=False),
                              name='shelf_read_has_finish_date'),
            m.CheckConstraint(condition=Q(show_in_profile=False) | Q(status='currently_reading'),
                              name='shelf_profile_only_currently_reading'),
        ]

    def __str__(self):
        return f'{self.user} - {self.book} ({self.status})'


class ShelfSettings(m.Model):
    class Visibility(m.TextChoices):
        ONLY_ME = 'only_me', 'Only me'
        EVERYONE = 'everyone', 'Everyone'
    user = m.OneToOneField(User, on_delete=m.CASCADE, related_name='shelf_settings')
    to_read_visibility = m.CharField(max_length=10, choices=Visibility.choices, default=Visibility.ONLY_ME)
    currently_reading_visibility = m.CharField(max_length=10, choices=Visibility.choices, default=Visibility.ONLY_ME)
    read_visibility = m.CharField(max_length=10, choices=Visibility.choices, default=Visibility.ONLY_ME)
    share_token = m.UUIDField(default=uuid.uuid4, unique=True, editable=False,help_text='Секретная часть публичной ссылки на полку')

    def __str__(self):
        return f'Shelf settings of {self.user}'