from django.core.exceptions import PermissionDenied
from django.db.models import Q, OuterRef, Sum, Count, Subquery, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.urls import reverse
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated, SAFE_METHODS, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet, ViewSet
from django.db import transaction
from django.db.models import F
from rest_framework.exceptions import ValidationError, NotFound
from rest_framework.permissions import IsAdminUser
from app.models import Country, City, Genre, Publisher, Shift, Supplier, Position, PaymentType, Library, ChillZoneOrder, \
    Product, ProductCategory, ShelfItem, ShelfSettings
from app.serializer.category import CategorySerializer
from app.serializer.city import CitiesSerializer, CitiesWriteSerializer
from app.serializer.country import CountrySerializer
from app.serializer.genre import GenresSerializer
from app.serializer.library import LibrariesSerializer, LibraryBookSerializer, LibraryBookCreateSerializer, \
    StockAdjustSerializer
from app.serializer.payment_type import PaymentTypesSerializer
from app.serializer.position import PositionSerializer
from app.serializer.product import ProductsSerializer, ProductsWriteSerializer
from app.serializer.publisher import PublisherSerializer
from app.serializer.shelf import ShelfItemSerializer, ShelfSettingsSerializer, ShelfUpdateSerializer, ShelfAddSerializer
from app.serializer.shift import ShiftSerializer
from app.serializer.supplier import SuppliersSerializer
from app import service, points, shelf
from app.models import Rental, RentalItem, BookQueue, Penalty, Notification, CartItem, Order, Book, LibraryBook, Author, \
    ChillZone, ChillZoneBookings
from app.pagination import Pagination
from app.permission import IsLibrarian, IsOrderManager, IsCourier, IsSuperUserOrReadOnly, IsLibrarianOfBookings, \
    IsCashier, IsSuperUser
from app.serializer.authors import AuthorsSerializer
from app.serializer.book import BookWriteSerializer, BookSerializer
from app.serializer.cart import CartItemSerializer, CartAddSerializer, CartQuantitySerializer
from app.serializer.chill_zone import ChillZoneWriteSerializer, ChillZoneSerializer, ChillZoneBookingSerializer, \
    ChillZoneBookingWriteSerializer, BookingConfirmSerializer, ChillOrderSerializer, ChillOrderCreateSerializer
from app.serializer.order import OrderSerializer, OrderCreateSerializer
from app.serializer.penalty import PenaltySerializer, PenaltyPaySerializer, NotificationSerializer
from app.serializer.points import BadgeCatalogSerializer, PointTransactionSerializer, PointsSummarySerializer

from app.serializer.receipt import chill_zone_receipt_text, chill_zone_product_receipt_text
from app.serializer.rent import RentalSerializer, RentalCreateSerializer, ActiveRentalItemSerializer, \
    ReturnRentalSerializer, QueueSerializer, QueueJoinSerializer, QueueNotifySerializer
from users.models import UserBadge, PointTransaction


class RentalViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Rental.objects.select_related('user','library').prefetch_related('items__book')
    serializer_class = RentalSerializer
    librarian_action=['confirm','mark_ready','hand_over','reject']

    def get_permissions(self):
        if self.action in self.librarian_action:
            return [IsLibrarian()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs=super().get_queryset()
        if not self.request.user.has_perm(IsLibrarian.codename):
            qs=qs.filter(user=self.request.user)
        status_value=self.request.query_params.get('status')
        return qs.filter(status=status_value) if status_value else qs

    def answer(self,rental):
        return Response(RentalSerializer(rental,context=self.get_serializer_context()).data)

    def create(self,request):
        serializer=RentalCreateSerializer(data=request.data,context={'request':request})
        serializer.is_valid(raise_exception=True)
        rental=serializer.save()
        return  Response(RentalSerializer(rental).data,status=status.HTTP_201_CREATED)

    @action(detail=True,methods=['post'])
    def cancel(self,request,pk=None):
        rental=service.close_rental(self.get_object().pk,request.user,Rental.Status.CANCELLED)
        return self.answer(rental)

    @action(detail=True,methods=['post'])
    def confirm(self,request,pk=None):
        return self.answer(service.move_rental(self.get_object().pk,request.user,'confirm'))

    @action(detail=True,methods=['post'])
    def hand_over(self,request,pk=None):
        return self.answer(service.move_rental(self.get_object().pk,request.user,'hand_over'))

    @action(detail=True,methods=['post'])
    def mark_ready(self,request,pk=None):
        return self.answer(service.move_rental(self.get_object().pk,request.user,'mark_ready'))

    @action(detail=True,methods=['post'])
    def reject(self,request,pk=None):
        return self.answer(service.close_rental(self.get_object().pk,request.user,Rental.Status.REJECTED))

class RentalItemViewSet(mixins.ListModelMixin,viewsets.GenericViewSet):
    queryset =(RentalItem.objects.filter(returned_at__isnull=True,rental__status=Rental.Status.ACTIVE).select_related('rental__user','rental__library','book'))
    serializer_class = ActiveRentalItemSerializer
    permission_classes = [IsLibrarian]
    filter_backends = [SearchFilter]
    search_fields=['rental__user__name','rental__user__username','rental__user__phone_number','rental__user__surname','book__name','book__isbn']

    @action(detail=True,methods=['post'])
    def mark_returned(self,request,pk=None):
        body=ReturnRentalSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        item=service.register_return(self.get_object().pk,request.user,body.validated_data['identity_confirmed'],body.validated_data['condition'])
        return Response({'id':item.id,'returned_at':item.returned_at})

class QueueViewSet(mixins.ListModelMixin,viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    queryset = BookQueue.objects.select_related('book','library')
    serializer_class = QueueSerializer

    def get_queryset(self):
        active=[BookQueue.Status.WAITING,BookQueue.Status.OFFERED]
        return super().get_queryset().filter(user=self.request.user,status__in=active)

    def list(self,request,*args,**kwargs):
        service.expire_stale_offers()
        return super().list(request,*args,**kwargs)

    def create(self,request):
        serializer=QueueJoinSerializer(data=request.data,context={'request':request})
        serializer.is_valid(raise_exception=True)
        return Response(QueueSerializer(serializer.save()).data,status=status.HTTP_201_CREATED)

    @action(detail=True,methods=['post'])
    def notify(self,request,pk=None):
        body=QueueNotifySerializer(data=request.data)
        body.is_valid(raise_exception=True)
        entry=self.get_object()
        entry.notify_me=body.validated_data['notify_me']
        entry.save(update_fields=['notify_me'])
        return Response(QueueSerializer(entry).data)

    @action(detail=True,methods=['post'])
    def leave(self,request,pk=None):
        service.leave_queue(request.user,self.get_object().pk)
        return Response(status=status.HTTP_204_NO_CONTENT)

class PenaltyViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Penalty.objects.select_related('book').order_by("-created_at")
    serializer_class = PenaltySerializer

    def get_queryset(self):
        is_librarian=self.request.user.has_perm(IsLibrarian.codename)
        service.sync_penalties(None if is_librarian else self.request.user)
        qs=super().get_queryset()
        return qs if is_librarian else qs.filter(user=self.request.user)

    @action(detail=True,methods=['post'])
    def pay(self,request,pk=None):
        body=PenaltyPaySerializer(data=request.data)
        body.is_valid(raise_exception=True)
        penalty=service.pay_penalty(request.user,int(pk),body.validated_data['payment_type'])
        return Response(PenaltySerializer(penalty).data)

class NotificationViewSet(mixins.ListModelMixin,viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    queryset=Notification.objects.all()
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

    @action(detail=True,methods=['post'])
    def read(self,request,pk=None):
        notification=self.get_object()
        notification.is_read=True
        notification.save(update_fields=['is_read'])
        return Response(NotificationSerializer(notification).data)

    @action(detail=False,methods=['post'])
    def read_all(self,request):
        self.get_queryset().update(is_read=True)
        return Response(status=status.HTTP_204_NO_CONTENT)

class CartViewSet(mixins.ListModelMixin,mixins.DestroyModelMixin,viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    queryset = CartItem.objects.select_related('book')
    serializer_class = CartItemSerializer

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

    def create(self,request):
        serializer=CartAddSerializer(data=request.data,context={'request':request})
        serializer.is_valid(raise_exception=True)
        return Response(CartItemSerializer(serializer.save()).data,status=status.HTTP_201_CREATED)

    def partial_update(self,request,pk=None):
        item=self.get_object()
        body=CartQuantitySerializer(data=request.data)
        body.is_valid(raise_exception=True)
        item.quantity=body.validated_data['quantity']
        item.save(update_fields=['quantity'])
        return Response(CartItemSerializer(item).data)

class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Order.objects.select_related('user','library','city').prefetch_related('items__book')
    serializer_class = OrderSerializer
    action_permission={
        'accept': IsOrderManager,
        'mark_ready':IsOrderManager,
        'complete':IsOrderManager,
        'take':IsCourier,
        'deliver':IsCourier}

    def get_permissions(self):
        permission=self.action_permission.get(self.action,IsAuthenticated)
        return [permission()]

    def get_queryset(self):
        user=self.request.user
        visible=Q(user=user)
        if user.has_perm(IsOrderManager.codename):
            visible |= Q(delivery_type=Order.DeliveryType.PICKUP)
        if user.has_perm(IsCourier.codename):
            visible |=Q(delivery_type=Order.DeliveryType.DELIVERY)
        qs=super().get_queryset().filter(visible)
        status_value=self.request.query_params.get('status')
        return qs.filter(status=status_value)if status_value else qs

    def create(self,request):
        serializer=OrderCreateSerializer(data=request.data,context={'request':request})
        serializer.is_valid(raise_exception=True)
        return Response(OrderSerializer(serializer.save()).data,status=status.HTTP_201_CREATED)

    def step(self,request,name):
        order=service.move_order(self.get_object().pk,request.user,name)
        return Response(OrderSerializer(order).data)

    @action(detail=True,methods=['post'])
    def accept(self,request,pk=None):
        return self.step(request,'accept')

    @action(detail=True,methods=['post'])
    def mark_ready(self,request,pk=None):
        return self.step(request,'mark_ready')

    @action(detail=True,methods=['post'])
    def complete(self,request,pk=None):
        return self.step(request,'complete')

    @action(detail=True,methods=['post'])
    def take(self,request,pk=None):
        return self.step(request,'take')

    @action(detail=True,methods=['post'])
    def deliver(self,request,pk=None):
        return self.step(request,'deliver')

ACTIVE=Rental.Status.ACTIVE
COMPLETED = Rental.Status.COMPLETED


class BooksViewSet(ModelViewSet):
    permission_classes = [IsSuperUserOrReadOnly]
    queryset = Book.objects.all()
    pagination_class = Pagination

    def get_serializer_class(self):
        if self.request.method in ('POST', 'PUT', 'PATCH'):
            return BookWriteSerializer
        return BookSerializer

    def get_queryset(self):
        params = self.request.query_params
        stock = LibraryBook.objects.filter(book=OuterRef('pk'))
        if params.get('library'):
            stock = stock.filter(library_id=params['library'])
        stock = (stock.values('book').annotate(total=Sum('quantity')).values('total'))
        qs = Book.objects.prefetch_related('author', 'genre').annotate(
            currently_borrowed=Count(
                'rental_items',
                filter=Q(
                    rental_items__rental__status=ACTIVE,
                    rental_items__returned_at__isnull=True
                ),
                distinct=True
            ),
            available_copies=Coalesce(
                Subquery(stock),
                Value(0)
            ),
        )
        if self.request.user.is_authenticated:
            mine = ShelfItem.objects.filter(
                user=self.request.user,
                book=OuterRef('pk')
            ).values('status')[:1]
            qs = qs.annotate(
                shelf_status=Subquery(mine)
            )
        if params.get('search'):
            qs = qs.filter(
                Q(name__icontains=params['search']) |
                Q(author__name__icontains=params['search'])
            )
        if params.get('genre'):
            qs = qs.filter(
                genre__name__icontains=params['genre']
            )
        if params.get('author'):
            qs = qs.filter(
                author__name__icontains=params['author']
            )

        if params.get('available') == 'true':
            qs = qs.filter(available_copies__gt=0)

        return qs.distinct().order_by('-rented', 'id')


class AuthorViewSet(ModelViewSet):
    permission_classes = [IsSuperUserOrReadOnly]
    queryset = Author.objects.all()
    serializer_class = AuthorsSerializer
    pagination_class = Pagination

    def get_queryset(self):
        qs = Author.objects.annotate(total_borrows=Count('books__rental_items',filter=Q(books__rental_items__rental__status__in=[ACTIVE,COMPLETED]),distinct=True),
                                     currently_borrowed=Count('books__rental_items',filter=Q(books__rental_items__rental__status=ACTIVE,
                                                                                             books__rental_items__returned_at__isnull=True),distinct=True),)
        search=self.request.query_params.get('search')
        if search:
            qs=qs.filter(name__icontains=search)
        return qs.order_by('-total_borrows', 'id')

def filter_by_branch(qs, user, library_field='library'):
    if user.is_superuser:
        return qs
    employee = getattr(user, 'employee_profile', None)
    if employee is None or employee.library_id is None:
        return qs.none()
    return qs.filter(**{library_field: employee.library_id})

class ChillZoneViewSet(ModelViewSet):
    permission_classes = [IsSuperUserOrReadOnly]
    queryset = ChillZone.objects.all()
    pagination_class = Pagination

    def get_serializer_class(self):
        if self.request.method in ('POST', 'PUT', 'PATCH'):
            return ChillZoneWriteSerializer
        return ChillZoneSerializer

    def get_queryset(self):
        qs=(ChillZone.objects.select_related('library__city').prefetch_related('library__shift','library__payment_type','library__book').order_by('id'))
        params=self.request.query_params
        if params.get('library'):
            qs=qs.filter(library_id=params['library'])
        if params.get('branch'):
            qs=qs.filter(branch=params['branch'])
        if params.get('available')=='true':
            qs=qs.filter(is_active=True,free_seats__gt=0)
        if params.get('seats','').isdigit():
            qs=qs.filter(is_active=True,free_seats__gte=int(params['seats']))
        return qs

class ChillZoneBookingViewSet(ReadOnlyModelViewSet):
    queryset = ChillZoneBookings.objects.select_related('user','reviewed_by','payment__payment_type','chill_zone__library__city')
    pagination_class = Pagination
    librarian_actions=['confirm','reject']

    def get_serializer_class(self):
        return ChillZoneBookingSerializer

    def get_permissions(self):
        if self.action in self.librarian_actions:
            return [IsLibrarianOfBookings()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs,user=super().get_queryset(),self.request.user
        if user.has_perm(IsLibrarianOfBookings.codename):
            qs=filter_by_branch(qs,user,library_field='chill_zone__library')
        else:
            qs=qs.filter(user=user)

        params=self.request.query_params
        if params.get('status'):
            qs=qs.filter(status=params['status'])
        if params.get('number','').isdigit():
            qs=qs.filter(id=int(params['number']))
        if params.get('search'):
            term=params['search']
            qs=qs.filter(user__phone_number__icontains=term) | qs.filter(user__name__icontains=term)
        return qs.order_by('-id')

    def create(self,request):
        serializer=ChillZoneBookingWriteSerializer(data=request.data,context={'request':request})
        serializer.is_valid(raise_exception=True)
        booking=serializer.save()
        return Response(ChillZoneBookingSerializer(booking).data,status=status.HTTP_201_CREATED)

    @action(detail=True,methods=['get'])
    def receipt(self,request,pk=None):
        booking=self.get_object()
        response=HttpResponse(chill_zone_receipt_text(booking),content_type='text/plain; charset=utf-8')
        response['Content-Disposition']=f'attachment; filename="receipt-{booking.id}.txt"'
        return response

    @action(detail=True,methods=['post'])
    def cancel(self,request,pk=None):
        booking=service.cancel_chill_booking(self.get_object().pk,request.user)
        return Response(ChillZoneBookingSerializer(booking).data)

    @action(detail=True,methods=['post'])
    def confirm(self,request,pk=None):
        body=BookingConfirmSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        booking=service.review_chill_booking(self.get_object().pk,request.user,'confirm',body.validated_data['identity_confirmed'])
        return Response(ChillZoneBookingSerializer(booking).data)

    @action(detail=True,methods=['post'])
    def reject(self,request,pk=None):
        booking=service.review_chill_booking(self.get_object().pk,request.user,'reject')
        return Response(ChillZoneBookingSerializer(booking).data)


class MyPointsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        points.evaluate_badges(request.user)
        data = points.points_summary(request.user)
        data['badges'] = UserBadge.objects.filter(user=request.user)
        return Response(PointsSummarySerializer(data).data)


class PointTransactionViewSet(ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = PointTransaction.objects.all()
    serializer_class = PointTransactionSerializer
    pagination_class = Pagination

    def get_queryset(self):
        qs = super().get_queryset().filter(user=self.request.user)
        reason = self.request.query_params.get('reason')
        return qs.filter(reason=reason) if reason else qs


class BadgeViewSet(ViewSet):
    permission_classes = [IsAuthenticated]
    def list(self, request):
        points.evaluate_badges(request.user)
        earned = {b.badge: b for b in UserBadge.objects.filter(user=request.user)}
        rows = [{
            'badge': code,
            'name': UserBadge.Badge(code).label,
            'description': points.BADGE_DESCRIPTIONS[code],
            'earned': code in earned,
            'earned_at': earned[code].earned_at if code in earned else None,
        } for code in UserBadge.Badge.values]
        if request.query_params.get('earned') == 'true':
            rows = [r for r in rows if r['earned']]
        return Response(BadgeCatalogSerializer(rows, many=True).data)

class CatalogViewSet(ModelViewSet):
    permission_classes = [IsSuperUserOrReadOnly]
    pagination_class = Pagination
    filter_backends = [SearchFilter]
    search_fields = ['name']


class CountryViewSet(CatalogViewSet):
    queryset = Country.objects.order_by('id')
    serializer_class = CountrySerializer


class CityViewSet(CatalogViewSet):
    queryset = City.objects.select_related('country').order_by('id')

    def get_serializer_class(self):
        if self.request.method in ('POST', 'PUT', 'PATCH'):
            return CitiesWriteSerializer
        return CitiesSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        country = self.request.query_params.get('country')
        return qs.filter(country_id=country) if country else qs


class GenreViewSet(CatalogViewSet):
    queryset = Genre.objects.order_by('id')
    serializer_class = GenresSerializer


class PublisherViewSet(CatalogViewSet):
    queryset = Publisher.objects.order_by('id')
    serializer_class = PublisherSerializer


class ShiftViewSet(CatalogViewSet):
    queryset = Shift.objects.order_by('id')
    serializer_class = ShiftSerializer


class PositionViewSet(CatalogViewSet):
    queryset = Position.objects.order_by('id')
    serializer_class = PositionSerializer


class PaymentTypeViewSet(CatalogViewSet):
    queryset = PaymentType.objects.order_by('id')
    serializer_class = PaymentTypesSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(is_active=True) if self.request.query_params.get('active') == 'true' else qs


class SupplierViewSet(CatalogViewSet):
    permission_classes = [IsAdminUser]
    queryset = Supplier.objects.order_by('id')
    serializer_class = SuppliersSerializer


class LibraryViewSet(CatalogViewSet):
    queryset = Library.objects.select_related('city').prefetch_related('book', 'shift', 'payment_type').order_by('id')
    serializer_class = LibrariesSerializer
    search_fields = ['name', 'address']

    def get_queryset(self):
        qs = super().get_queryset()
        city = self.request.query_params.get('city')
        return qs.filter(city_id=city) if city else qs


class LibraryBookViewSet(ModelViewSet):
    queryset = LibraryBook.objects.select_related('library', 'book')
    pagination_class = Pagination
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_serializer_class(self):
        return LibraryBookCreateSerializer if self.action == 'create' else LibraryBookSerializer

    def get_permissions(self):
        if self.action == 'adjust_stock':
            return [IsLibrarian()]
        return [IsSuperUserOrReadOnly()]

    def get_queryset(self):
        qs, params = super().get_queryset(), self.request.query_params
        if params.get('library'):
            qs = qs.filter(library_id=params['library'])
        if params.get('book'):
            qs = qs.filter(book_id=params['book'])
        if self.action == 'adjust_stock':
            qs = filter_by_branch(qs, self.request.user)
        return qs.order_by('id')

    @action(detail=True, methods=['post'])
    def adjust_stock(self, request, pk=None):
        body = StockAdjustSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        delta = body.validated_data['delta']
        link = self.get_object()
        with transaction.atomic():
            locked = LibraryBook.objects.select_for_update().get(pk=link.pk)
            if locked.quantity + delta < 0:
                raise ValidationError({'delta': 'The final quantity cannot be negative.'})
            if delta > 0:
                service.add_copies(locked.library, locked.book, delta)
            elif delta < 0:
                LibraryBook.objects.filter(pk=locked.pk).update(quantity=F('quantity') + delta)
        return Response(LibraryBookSerializer(LibraryBook.objects.get(pk=link.pk)).data)


class CashierOnlyReadMixin:
    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsCashier()]
        return [IsSuperUser()]

class ProductCategoryViewSet(CashierOnlyReadMixin, ModelViewSet):
    queryset = ProductCategory.objects.order_by('id')
    serializer_class = CategorySerializer
    pagination_class = Pagination
    filter_backends = [SearchFilter]
    search_fields = ['name']


class ProductViewSet(CashierOnlyReadMixin, ModelViewSet):
    queryset = Product.objects.prefetch_related('category', 'supplier').order_by('id')
    pagination_class = Pagination
    filter_backends = [SearchFilter]
    search_fields = ['name', 'category__name']

    def get_serializer_class(self):
        if self.request.method in ('POST', 'PUT', 'PATCH'):
            return ProductsWriteSerializer
        return ProductsSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_superuser:
            qs = qs.filter(is_active=True)
        category = self.request.query_params.get('category')
        return qs.filter(category=category).distinct() if category else qs.distinct()


class ChillOrderViewSet(ReadOnlyModelViewSet):
    queryset = ChillZoneOrder.objects.select_related(
        'booking__user', 'booking__chill_zone__library', 'cashier', 'payment__payment_type'
    ).prefetch_related('items__product')
    serializer_class = ChillOrderSerializer
    permission_classes = [IsCashier]
    pagination_class = Pagination

    def get_queryset(self):
        qs = filter_by_branch(super().get_queryset(), self.request.user,
                              library_field='booking__chill_zone__library')  # только свой филиал
        params = self.request.query_params
        if params.get('number', '').isdigit():
            qs = qs.filter(id=int(params['number']))
        if params.get('booking', '').isdigit():
            qs = qs.filter(booking_id=int(params['booking']))
        if params.get('search'):
            term = params['search']
            qs = qs.filter(booking__user__phone_number__icontains=term) | qs.filter(booking__user__name__icontains=term)
        return qs.order_by('-id')

    def create(self, request):
        serializer = ChillOrderCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        booking = serializer.validated_data['booking']
        same_branch = filter_by_branch(ChillZoneBookings.objects.filter(pk=booking.pk), request.user,
                                       library_field='chill_zone__library').exists()
        if not same_branch:
            raise PermissionDenied('This booking belongs to another branch.')
        return Response(ChillOrderSerializer(serializer.save()).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def find_booking(self, request):
        number = request.query_params.get('number', '')
        qs = ChillZoneBookings.objects.select_related('user', 'reviewed_by', 'payment__payment_type',
                                                      'chill_zone__library__city')
        qs = filter_by_branch(qs.filter(status=ChillZoneBookings.Status.CONFIRMED), request.user,
                              library_field='chill_zone__library')
        qs = qs.filter(id=int(number)) if number.isdigit() else qs.none()
        return Response(ChillZoneBookingSerializer(qs, many=True).data)

    @action(detail=True, methods=['get'])
    def receipt(self, request, pk=None):
        order = self.get_object()
        response = HttpResponse(chill_zone_product_receipt_text(order), content_type='text/plain; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="products-receipt-{order.id}.txt"'
        return response


class ShelfViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.DestroyModelMixin,viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    queryset = ShelfItem.objects.all()
    serializer_class = ShelfItemSerializer
    pagination_class = Pagination

    def get_queryset(self):
        if self.action == 'list':
            return shelf.filtered_items(self.request.user, self.request.query_params)
        return (ShelfItem.objects.filter(user=self.request.user)
                .select_related('book').prefetch_related('book__author'))

    def create(self, request):
        serializer = ShelfAddSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        item = serializer.save()
        code = status.HTTP_201_CREATED if serializer.created else status.HTTP_200_OK
        return Response(ShelfItemSerializer(item).data, status=code)

    def partial_update(self, request, pk=None):
        body = ShelfUpdateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        item = shelf.update_item(request.user, self.get_object(), body.validated_data.get('status'),
                                 body.validated_data.get('finished_at'))
        return Response(ShelfItemSerializer(item).data)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        data = shelf.counts(request.user)
        data['total'] = sum(data.values())
        return Response(data)

    @action(detail=False, methods=['get'])
    def by_book(self, request):
        book = request.query_params.get('book', '')
        item = ShelfItem.objects.filter(user=request.user, book_id=int(book)).first() if book.isdigit() else None
        return Response(ShelfItemSerializer(item).data if item else {'status': None})

    @action(detail=False, methods=['get'])
    def featured(self, request):
        return Response(ShelfItemSerializer(shelf.featured_books(request.user), many=True).data)

    @action(detail=True, methods=['post'])
    def feature(self, request, pk=None):
        return Response(ShelfItemSerializer(shelf.set_featured(request.user, self.get_object().pk, True)).data)

    @action(detail=True, methods=['post'])
    def unfeature(self, request, pk=None):
        return Response(ShelfItemSerializer(shelf.set_featured(request.user, self.get_object().pk, False)).data)

    @action(detail=False, methods=['get', 'patch'], url_path='settings')
    def visibility(self, request):
        settings = shelf.get_settings(request.user)
        if request.method == 'PATCH':
            serializer = ShelfSettingsSerializer(settings, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
        return Response(ShelfSettingsSerializer(settings).data)

    @action(detail=False, methods=['get'])
    def share(self, request):
        settings = shelf.get_settings(request.user)
        enabled = shelf.share_enabled(settings)
        link = request.build_absolute_uri(reverse('shelf-public', args=[settings.share_token])) if enabled else None
        return Response({'enabled': enabled, 'link': link, 'lists': shelf.visible_statuses(settings)})

    @action(detail=False, methods=['get'], url_path='share/image')
    def share_image(self, request):
        settings = shelf.get_settings(request.user)
        if not shelf.share_enabled(settings):
            raise PermissionDenied('Set at least one list to "Everyone" to share your shelf.')
        response = HttpResponse(shelf.build_share_svg(request.user, settings), content_type='image/svg+xml')
        response['Content-Disposition'] = 'attachment; filename="my-shelf.svg"'
        return response


class PublicShelfView(GenericAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    pagination_class = Pagination
    serializer_class = ShelfItemSerializer

    def get(self, request, token):
        settings = ShelfSettings.objects.select_related('user').filter(share_token=token).first()
        visible = shelf.visible_statuses(settings) if settings else []
        if not visible:
            raise NotFound('This shelf is private or does not exist.')
        owner, totals = settings.user, shelf.counts(settings.user)
        data = {
            'owner': shelf.display_name(owner),
            'lists': [{'status': s, 'label': ShelfItem.Status(s).label, 'count': totals[s]} for s in visible],
        }
        if ShelfItem.Status.CURRENTLY_READING in visible:
            data['featured'] = ShelfItemSerializer(shelf.featured_books(owner), many=True).data
        status_param = request.query_params.get('status')
        if status_param:
            if status_param not in visible:
                raise NotFound('This list is private or does not exist.')
            paginator = self.pagination_class()
            page = paginator.paginate_queryset(
                shelf.filtered_items(owner, request.query_params, status=status_param), request, view=self)
            data['items'] = paginator.get_paginated_response(ShelfItemSerializer(page, many=True).data).data
        return Response(data)