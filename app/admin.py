from django.contrib import admin
from app.models import ShelfItem, Country, Category, City, Publisher, Shift, Supplier, Position, PaymentType, Payment, \
    Genre, Author, Book, Library, LibraryBook, ChillZone, ChillZoneBookings, Product, ProductCategory, Subscription, \
    Rental, RentalItem, BookQueue, Penalty, Notification, Wishlist, CartItem, Order, OrderItem, ChillZoneOrderItem, \
    ChillZoneOrder, ShelfSettings

# Register your models here.

admin.site.register(ShelfItem)
admin.site.register(Country)
admin.site.register(Category)
admin.site.register(City)
admin.site.register(Publisher)
admin.site.register(Shift)
admin.site.register(Supplier)
admin.site.register(Position)
admin.site.register(PaymentType)
admin.site.register(Genre)
admin.site.register(Author)
admin.site.register(Book)
admin.site.register(Library)
admin.site.register(LibraryBook)
admin.site.register(Payment)
admin.site.register(ChillZone)
admin.site.register(ChillZoneBookings)
admin.site.register(Product)
admin.site.register(ProductCategory)
admin.site.register(Subscription)
admin.site.register(Rental)
admin.site.register(RentalItem)
admin.site.register(BookQueue)
admin.site.register(Penalty)
admin.site.register(Notification)
admin.site.register(Wishlist)
admin.site.register(CartItem)
admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(ChillZoneOrderItem)
admin.site.register(ChillZoneOrder)
admin.site.register(ShelfSettings)