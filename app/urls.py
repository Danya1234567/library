from django.urls import path
from rest_framework.routers import DefaultRouter

from app.views import RentalViewSet, RentalItemViewSet, QueueViewSet, PenaltyViewSet, NotificationViewSet, CartViewSet, \
    OrderViewSet, BooksViewSet, AuthorViewSet, ChillZoneViewSet, ChillZoneBookingViewSet, PointTransactionViewSet, \
    BadgeViewSet, MyPointsView, ShelfViewSet, PublicShelfView

router = DefaultRouter()
router.register('rentals', RentalViewSet, basename='rental')
router.register('rental_items', RentalItemViewSet, basename='rental-item')
router.register('queue', QueueViewSet, basename='queue')
router.register('penalties', PenaltyViewSet, basename='penalty')
router.register('notifications', NotificationViewSet, basename='notification')
router.register('cart', CartViewSet, basename='cart')
router.register('orders', OrderViewSet, basename='order')
router.register('books', BooksViewSet, basename='book')
router.register('authors', AuthorViewSet, basename='author')
router.register('chill_zones', ChillZoneViewSet, basename='chill-zone')
router.register('chill_zone_bookings', ChillZoneBookingViewSet, basename='chill-zone-booking')
router.register('point_transactions', PointTransactionViewSet, basename='point-transaction')
router.register('badges', BadgeViewSet, basename='badge')
router.register('shelf', ShelfViewSet, basename='shelf')
path('shelf/public/<uuid:token>/', PublicShelfView.as_view(), name='shelf-public')
urlpatterns = router.urls + [path('points/me/', MyPointsView.as_view())]