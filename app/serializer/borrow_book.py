from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from django.db.models import F

from app.models import Library, Payment, BorrowOneBook, LibraryBook, Book, BorrowABook
from app.serializer.book import BooksSerializer
from users.models import Employee, User


class LibraryShortsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Library
        fields = ['address', 'branch', 'city']


class EmployeeShortsSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='user.name', read_only=True)
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)
    position = serializers.SlugRelatedField(slug_field='name_of_position', read_only=True)
    shift = serializers.SlugRelatedField(many=True, slug_field='name_of_shift', read_only=True)

    class Meta:
        model = Employee
        fields = ['name', 'phone_number', 'shift', 'position', ]


class PaymentsShortsSerializer(serializers.ModelSerializer):
    payment_type = serializers.SlugRelatedField(
        slug_field='name',
        read_only=True)

    class Meta:
        model = Payment
        fields = ['price', 'payment_type']


class BorrowABooksMinimalSerializer(serializers.ModelSerializer):
    library = LibraryShortsSerializer(read_only=True)
    client_card = serializers.SlugRelatedField(
        slug_field='phone_number',
        read_only=True)

    class Meta:
        model = BorrowABook
        fields = ['id', 'borrow_at', 'until', 'library', 'client_card']


class BorrowABookStaffSerializer(serializers.ModelSerializer):
    library = LibraryShortsSerializer(read_only=True)
    employee = EmployeeShortsSerializer(read_only=True)
    client_card = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    days_overdue = serializers.SerializerMethodField()
    debt_amount = serializers.SerializerMethodField()

    def get_client_card(self, obj):
        user = obj.client_card
        return {'id': user.id, 'username': user.username, 'name': user.name, 'surname': user.surname,
                'phone_number': user.phone_number}

    payment = PaymentsShortsSerializer(read_only=True)
    book = serializers.SlugRelatedField(many=True, slug_field='name', read_only=True)

    def get_is_overdue(self, obj):
        if obj.until is None:
            return False
        return obj.until < timezone.now().date() and obj.borrow_book.filter(returned_at__isnull=True).exists()

    def get_days_overdue(self, obj):
        if not self.get_is_overdue(obj):
            return 0
        return (timezone.now().date() - obj.until).days

    def get_debt_amount(self, obj):
        days_late = self.get_days_overdue(obj)
        if days_late == 0:
            return '0.00'
        first_book = obj.borrow_book.select_related('book').first()
        fine_per_day = first_book.book.rent_price * Decimal('0.10')
        return str((fine_per_day * days_late).quantize(Decimal('0.01')))

    class Meta:
        model = BorrowABook
        fields = '__all__'


class BorrowABookClientSerializer(serializers.ModelSerializer):
    library = LibraryShortsSerializer(read_only=True)
    client_card = serializers.SerializerMethodField()

    def get_client_card(self, obj):
        user = obj.client_card
        return {'id': user.id, 'username': user.username, 'name': user.name, 'surname': user.surname,
                'phone_number': user.phone_number}

    employee = EmployeeShortsSerializer(read_only=True)
    payment = PaymentsShortsSerializer(read_only=True)
    book = serializers.SlugRelatedField(many=True, slug_field='name', read_only=True)
    is_overdue = serializers.SerializerMethodField()
    days_overdue = serializers.SerializerMethodField()
    debt_amount = serializers.SerializerMethodField()

    def get_is_overdue(self, obj):
        if obj.until is None:
            return False
        return obj.until < timezone.now().date() and obj.borrow_book.filter(returned_at__isnull=True).exists()

    def get_days_overdue(self, obj):
        if not self.get_is_overdue(obj):
            return 0
        return (timezone.now().date() - obj.until).days

    def get_debt_amount(self, obj):
        days_late = self.get_days_overdue(obj)
        if days_late == 0:
            return '0.00'
        first_book = obj.borrow_book.select_related('book').first()
        fine_per_day = first_book.book.rent_price * Decimal('0.10')
        return str((fine_per_day * days_late).quantize(Decimal('0.01')))

    class Meta:
        model = BorrowABook
        fields = '__all__'


class BorrowABookSerializer(serializers.ModelSerializer):
    book = (
        BooksSerializer(read_only=True))
    borrow_at = BorrowABooksMinimalSerializer(read_only=True)

    class Meta:
        model = BorrowOneBook
        fields = '__all__'


def calculate_price(books, transaction_type, days):
    if transaction_type == 'purchase':
        return sum(book.price for book in books)
    return sum(book.rent_price * days for book in books)


def check_books_available(library, books):
    links = LibraryBook.objects.select_for_update().filter(library=library, book__in=books)
    quantity_by_book = {link.book_id: link.quantity for link in links}

    for book in books:
        if quantity_by_book.get(book.id, 0) < 1:
            raise serializers.ValidationError(f'Book "{book.name}" not available in this library.')


class BorrowABooksWriteSerializer(serializers.ModelSerializer):
    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all(), allow_null=True, required=False)
    client_card = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), allow_null=True, required=False)
    book = serializers.PrimaryKeyRelatedField(queryset=Books.objects.all(), many=True, write_only=True)
    payment_type = serializers.PrimaryKeyRelatedField(queryset=PaymentTypes.objects.all(), write_only=True)

    class Meta:
        model = BorrowABook
        fields = ['id', 'transaction_type', 'borrow_at', 'until', 'library', 'employee', 'client_card', 'book',
                  'payment_type']

    def validate(self, data):
        if data.get('transaction_type') == 'rent' and not data.get('until'):
            raise serializers.ValidationError({'until': 'For rent you must enter date until.'})
        if data.get('transaction_type') == 'purchase':
            data['until'] = None
        return data

    def create(self, validated_data):
        books = validated_data.pop('book')
        payment_type = validated_data.pop('payment_type')
        library = validated_data['library']

        days = 1
        if validated_data.get('until'):
            days = (validated_data['until'] - validated_data['borrow_at']).days or 1

        total_price = calculate_price(books, validated_data.get('transaction_type', 'rent'), days)

        with transaction.atomic():
            check_books_available(library, books)

            payment = Payment.objects.create(price=total_price, is_success=True, payment_type=payment_type)
            borrow_batch = BorrowABook.objects.create(payment=payment, **validated_data)

            BorrowOneBook.objects.bulk_create([
                BorrowOneBook(borrow_at=borrow_batch, book=book) for book in books
            ])

            LibraryBook.objects.filter(library=library, book__in=books).update(quantity=F('quantity') - 1)
            Book.objects.filter(id__in=[b.id for b in books]).update(rented=F('rented') + 1)

        return borrow_batch














