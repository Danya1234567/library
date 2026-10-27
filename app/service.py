from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from app import points
from app.models import (Book, BookQueue, CartItem, ChillZone, ChillZoneBookings, Library, LibraryBook,
                        Notification, Order, OrderItem, Payment, Penalty, Rental, RentalItem, Subscription,
                        ChillZoneOrder, ChillZoneOrderItem)

MAX_RENT_DAYS = 30
FINE_RATE = Decimal('0.10')
OFFER_HOURS = 48
DELIVERY_FEE_BRANCH = Decimal('15000.00')
DELIVERY_FEE_POST = Decimal('30000.00')


def today():
    return timezone.localdate()


def notify(user, title, message=''):
    Notification.objects.create(user=user, title=title, message=message)

def get_active_subscription(user):
    d = today()
    return (Subscription.objects.
            filter(user=user, status='Active', start_date__lte=d, end_date__gte=d).order_by('-end_date').first())

def require_member(user):

    sub = get_active_subscription(user)
    if sub is None:
        raise PermissionDenied('Only members with an active subscription can rent books.')
    return sub


def slots_used(sub):
    return (RentalItem.objects.filter(rental__subscription=sub)
            .exclude(rental__status__in=[Rental.Status.REJECTED, Rental.Status.CANCELLED])
            .count())


def slots_left(sub):
    return max(sub.books_limit - slots_used(sub), 0)

def fine_per_day(book):
    return (book.rent_price * FINE_RATE).quantize(Decimal('0.01'))


def _sync_item_penalty(item, day):
    rental = item.rental
    last = item.penalties.order_by('-end_date').first()
    covered_until = last.end_date if last else rental.until
    if day <= covered_until:
        return
    per_day = fine_per_day(item.book)
    if last and last.status == Penalty.Status.UNPAID:
        last.end_date = day
        last.total_amount = per_day * (day - last.start_date).days
        last.save(update_fields=['end_date', 'total_amount'])
    else:
        Penalty.objects.create(
            user=rental.user, book=item.book, rental_item=item,
            start_date=covered_until, end_date=day,
            total_amount=per_day * (day - covered_until).days,
        )


def sync_penalties(user=None):
    day = today()
    with transaction.atomic():
        qs = (RentalItem.objects
              .filter(returned_at__isnull=True, rental__status=Rental.Status.ACTIVE, rental__until__lt=day)
              .select_related('rental', 'book'))
        if user is not None:
            qs = qs.filter(rental__user=user)
        for item in qs.select_for_update(of=('self',)):
            _sync_item_penalty(item, day)


def has_unpaid_penalty(user):
    sync_penalties(user)
    return Penalty.objects.filter(user=user, status=Penalty.Status.UNPAID).exists()


def create_online_payment(amount, payment_type):
    return Payment.objects.create(price=amount, is_success=True, payment_type=payment_type)


@transaction.atomic
def pay_penalty(user, penalty_id, payment_type):
    sync_penalties(user)
    penalty = Penalty.objects.select_for_update().filter(pk=penalty_id, user=user).first()
    if penalty is None:
        raise ValidationError('Penalty not found.')
    if penalty.status == Penalty.Status.PAID:
        raise ValidationError('This penalty is already paid.')
    penalty.payment = create_online_payment(penalty.total_amount, payment_type)
    penalty.status = Penalty.Status.PAID
    penalty.save(update_fields=['payment', 'status'])
    return penalty

def _offer_or_restock(link):
    nxt = (BookQueue.objects.select_for_update()
           .filter(library_id=link.library_id, book_id=link.book_id, status=BookQueue.Status.WAITING)
           .order_by('created_at').first())
    if nxt is None:
        link.quantity += 1
        link.save(update_fields=['quantity'])
        return
    now = timezone.now()
    nxt.status = BookQueue.Status.OFFERED
    nxt.offered_at = now
    nxt.expires_at = now + timedelta(hours=OFFER_HOURS)
    nxt.save(update_fields=['status', 'offered_at', 'expires_at'])
    if nxt.notify_me:
        notify(nxt.user, 'Your turn in the queue',
               f'"{nxt.book.name}" is waiting for you. Send a rental request within {OFFER_HOURS} hours.')


def release_copy(library, book):
    with transaction.atomic():
        link = LibraryBook.objects.select_for_update().get(library=library, book=book)
        _offer_or_restock(link)


@transaction.atomic
def add_copies(library, book, count):
    for _ in range(count):
        release_copy(library, book)


def expire_stale_offers():
    stale = list(BookQueue.objects
                 .filter(status=BookQueue.Status.OFFERED, expires_at__lt=timezone.now())
                 .values_list('id', 'library_id', 'book_id'))
    for entry_id, lib_id, book_id in stale:
        with transaction.atomic():
            link = LibraryBook.objects.select_for_update().get(library_id=lib_id, book_id=book_id)
            entry = (BookQueue.objects.select_for_update().select_related('user', 'book')
                     .filter(pk=entry_id, status=BookQueue.Status.OFFERED, expires_at__lt=timezone.now())
                     .first())
            if entry is None:
                continue
            entry.status = BookQueue.Status.EXPIRED
            entry.save(update_fields=['status'])
            notify(entry.user, 'Queue turn expired',
                   f'You did not confirm "{entry.book.name}" in {OFFER_HOURS} hours.')
            _offer_or_restock(link)


def queue_position(entry):
    if entry.status == BookQueue.Status.OFFERED:
        return 0
    return 1 + BookQueue.objects.filter(
        library_id=entry.library_id, book_id=entry.book_id,
        status=BookQueue.Status.WAITING, created_at__lt=entry.created_at).count()


@transaction.atomic
def join_queue(user, book, library):
    require_member(user)
    expire_stale_offers()
    link = LibraryBook.objects.select_for_update().filter(library=library, book=book).first()
    if link is None:
        raise ValidationError('This book is not available in this branch.')
    if link.quantity > 0:
        raise ValidationError('A copy is available right now, you can rent it without the queue.')
    active = [BookQueue.Status.WAITING, BookQueue.Status.OFFERED]
    if BookQueue.objects.filter(user=user, book=book, library=library, status__in=active).exists():
        raise ValidationError('You are already in this queue.')
    entry = BookQueue.objects.create(user=user, book=book, library=library)
    notify(user, 'You joined the queue', f'You are #{queue_position(entry)} in line for "{book.name}".')
    return entry


@transaction.atomic
def leave_queue(user, entry_id):
    entry = BookQueue.objects.filter(pk=entry_id, user=user).first()
    if entry is None:
        raise ValidationError('Queue entry not found.')
    link = LibraryBook.objects.select_for_update().get(library_id=entry.library_id, book_id=entry.book_id)
    entry = BookQueue.objects.select_for_update().get(pk=entry.pk)
    if entry.status not in (BookQueue.Status.WAITING, BookQueue.Status.OFFERED):
        raise ValidationError('You have already left this queue.')
    was_offered = entry.status == BookQueue.Status.OFFERED
    entry.status = BookQueue.Status.LEFT
    entry.save(update_fields=['status'])
    if was_offered:
        _offer_or_restock(link)
    return entry

@transaction.atomic
def create_rental(user, library, start_date, until, books):
    sub = require_member(user)
    sub = Subscription.objects.select_for_update().get(pk=sub.pk)

    if has_unpaid_penalty(user):
        raise ValidationError('You have an unpaid penalty. Pay it before renting new books.')
    left = slots_left(sub)
    if len(books) > left:
        raise ValidationError(f'Rental limit: you have {left} of {sub.books_limit} books left on your subscription.')

    expire_stale_offers()
    ids = [b.id for b in books]
    links = {l.book_id: l for l in LibraryBook.objects.select_for_update().filter(library=library, book_id__in=ids)}
    offers = {e.book_id: e for e in BookQueue.objects.select_for_update()
              .filter(user=user, library=library, book_id__in=ids, status=BookQueue.Status.OFFERED)}

    for book in books:
        if not book.is_allowed:
            raise ValidationError(f'Book "{book.name}" is not available for rent.')
        link = links.get(book.id)
        if book.id not in offers and (link is None or link.quantity < 1):
            raise ValidationError(f'Book "{book.name}" is rented out in this branch. Join the queue.')

    rental = Rental.objects.create(user=user, subscription=sub, library=library,
                                   start_date=start_date, until=until)
    RentalItem.objects.bulk_create([RentalItem(rental=rental, book=b) for b in books])
    for book in books:
        if book.id in offers:
            offers[book.id].status = BookQueue.Status.FULFILLED
            offers[book.id].save(update_fields=['status'])
        else:
            link = links[book.id]
            link.quantity -= 1
            link.save(update_fields=['quantity'])
    return rental


RENTAL_FLOW = {
    'confirm': (Rental.Status.SENT, Rental.Status.PREPARING),
    'mark_ready': (Rental.Status.PREPARING, Rental.Status.READY),
    'hand_over': (Rental.Status.READY, Rental.Status.ACTIVE),
}


@transaction.atomic
def move_rental(rental_id, actor, action):
    src, dst = RENTAL_FLOW[action]
    rental = Rental.objects.select_for_update().select_related('user').get(pk=rental_id)
    if rental.status != src:
        raise ValidationError(f'Action "{action}" is not possible: rental is "{rental.status}".')
    rental.status = dst
    rental.processed_by = actor
    rental.save(update_fields=['status', 'processed_by', 'updated_at'])
    if action == 'confirm':
        notify(rental.user, 'Rental request confirmed', 'Your books are being prepared.')
    elif action == 'mark_ready':
        notify(rental.user, 'Ready for pick up', f'Your books are ready at branch "{rental.library.name}".')
    else:
        Book.objects.filter(rental_items__rental=rental).update(rented=F('rented') + 1)
    return rental


@transaction.atomic
def close_rental(rental_id, actor, new_status):
    rental = Rental.objects.select_for_update().select_related('user', 'library').get(pk=rental_id)
    allowed = [Rental.Status.SENT, Rental.Status.PREPARING]
    if new_status == Rental.Status.CANCELLED:
        if rental.user_id != actor.id:
            raise PermissionDenied('You can cancel only your own request.')
        allowed = [Rental.Status.SENT]
    if rental.status not in allowed:
        raise ValidationError(f'Rental is already "{rental.status}".')
    for item in rental.items.select_related('book'):
        release_copy(rental.library, item.book)
    rental.status = new_status
    rental.processed_by = actor if new_status == Rental.Status.REJECTED else rental.processed_by
    rental.save(update_fields=['status', 'processed_by', 'updated_at'])
    if new_status == Rental.Status.REJECTED:
        notify(rental.user, 'Rental request rejected', f'Request #{rental.pk} was rejected by the librarian.')
    return rental


@transaction.atomic
def register_return(item_id, actor, identity_confirmed, condition=RentalItem.Condition.GOOD):
    if not identity_confirmed:
        raise ValidationError({'identity_confirmed': 'Confirm the member identity first.'})
    item = (RentalItem.objects.select_for_update().select_related('rental', 'book')
            .filter(pk=item_id).first())
    if item is None:
        raise ValidationError('Rental item not found.')
    rental = item.rental
    if rental.status != Rental.Status.ACTIVE or item.returned_at is not None:
        raise ValidationError('This book is not in the active rentals.')
    day = today()
    _sync_item_penalty(item, day)
    item.returned_at = day
    item.returned_by = actor
    item.return_condition = condition
    item.save(update_fields=['returned_at', 'returned_by', 'return_condition'])
    release_copy(rental.library, item.book)
    if not rental.items.filter(returned_at__isnull=True).exists():
        rental.status = Rental.Status.COMPLETED
        rental.save(update_fields=['status', 'updated_at'])
    points.on_book_returned(item)
    return item

def pick_dispatch_library(cart, city):
    ok = []
    for lib in Library.objects.all():
        stock = dict(lib.library_books.values_list('book_id', 'quantity'))
        if all(stock.get(ci.book_id, 0) >= ci.quantity for ci in cart):
            ok.append(lib)
    local = [l for l in ok if l.city_id == city.id]
    if local:
        return local[0], Order.DeliveryMethod.BRANCH
    if ok:
        return ok[0], Order.DeliveryMethod.POST
    return None


@transaction.atomic
def create_order(user, *, delivery_type, payment_type, contact_name, contact_phone,
                 library=None, city=None, address=''):
    cart = list(CartItem.objects.select_related('book').filter(user=user))
    if not cart:
        raise ValidationError('Your cart is empty.')
    for ci in cart:
        if not ci.book.is_allowed:
            raise ValidationError(f'Book "{ci.book.name}" is not for sale.')

    method, fee = None, Decimal('0.00')
    if delivery_type == Order.DeliveryType.PICKUP:
        if library is None:
            raise ValidationError({'library': 'Choose a branch for pick up.'})
    else:
        if city is None or not address:
            raise ValidationError({'address': 'Choose a city and enter the delivery address.'})
        picked = pick_dispatch_library(cart, city)
        if picked is None:
            raise ValidationError('No branch has all these books in stock.')
        library, method = picked
        fee = DELIVERY_FEE_BRANCH if method == Order.DeliveryMethod.BRANCH else DELIVERY_FEE_POST

    links = {l.book_id: l for l in LibraryBook.objects.select_for_update()
             .filter(library=library, book_id__in=[c.book_id for c in cart])}
    for ci in cart:
        link = links.get(ci.book_id)
        if link is None or link.quantity < ci.quantity:
            raise ValidationError(f'Not enough copies of "{ci.book.name}" in the chosen branch.')

    subtotal = sum((ci.book.price * ci.quantity for ci in cart), Decimal('0.00'))
    total = subtotal + fee
    payment = create_online_payment(total, payment_type)
    order = Order.objects.create(
        user=user, delivery_type=delivery_type, delivery_method=method, library=library,
        city=city, address=address, contact_name=contact_name, contact_phone=contact_phone,
        delivery_fee=fee, total_price=total, payment=payment, status=Order.Status.SENT)
    OrderItem.objects.bulk_create([
        OrderItem(order=order, book=ci.book, quantity=ci.quantity, unit_price=ci.book.price) for ci in cart])
    for ci in cart:
        link = links[ci.book_id]
        link.quantity -= ci.quantity
        link.save(update_fields=['quantity'])
    CartItem.objects.filter(user=user).delete()
    points.on_books_purchased(order)
    return order


ORDER_FLOW = {
    'accept': (Order.DeliveryType.PICKUP, Order.Status.SENT, Order.Status.PREPARING),
    'mark_ready': (Order.DeliveryType.PICKUP, Order.Status.PREPARING, Order.Status.READY),
    'complete': (Order.DeliveryType.PICKUP, Order.Status.READY, Order.Status.COMPLETED),
    'take': (Order.DeliveryType.DELIVERY, Order.Status.SENT, Order.Status.ON_THE_WAY),
    'deliver': (Order.DeliveryType.DELIVERY, Order.Status.ON_THE_WAY, Order.Status.DELIVERED),
}


@transaction.atomic
def move_order(order_id, actor, action):
    kind, src, dst = ORDER_FLOW[action]
    order = Order.objects.select_for_update().select_related('user', 'library').get(pk=order_id)
    if order.delivery_type != kind:
        raise ValidationError(f'Action "{action}" does not apply to this order type.')
    if order.status != src:
        raise ValidationError(f'Action "{action}" is not possible: order is "{order.status}".')
    order.status = dst
    if kind == Order.DeliveryType.DELIVERY:
        order.courier = actor
        order.save(update_fields=['status', 'courier'])
    else:
        order.processed_by = actor
        order.save(update_fields=['status', 'processed_by'])
    if action == 'mark_ready':
        notify(order.user, 'Order is ready', f'Order #{order.pk} can be picked up at "{order.library.name}".')
    elif action == 'take':
        notify(order.user, 'Order is on the way', f'Order #{order.pk} was handed to the courier.')
    elif action == 'deliver':
        notify(order.user, 'Order delivered', f'Order #{order.pk} was delivered.')
    return order

@transaction.atomic
def create_chill_booking(user, zone, seats, payment_type):
    zone = ChillZone.objects.select_for_update().get(pk=zone.pk)
    if not zone.is_active:
        raise ValidationError('This zone is currently unavailable.')
    if seats > zone.free_seats:
        raise ValidationError({'seats': 'Not enough available spaces.'})
    total = zone.price * seats
    payment = create_online_payment(total, payment_type)
    zone.free_seats -= seats
    zone.save(update_fields=['free_seats'])
    booking = ChillZoneBookings.objects.create(
        user=user, chill_zone=zone, seats=seats, total_price=total, payment=payment,
        status=ChillZoneBookings.Status.PENDING)
    points.on_chill_booked(booking)     # бейдж Chill zone guest
    return booking


def _release_zone_seats(booking):
    zone = ChillZone.objects.select_for_update().get(pk=booking.chill_zone_id)
    zone.free_seats = min(zone.free_seats + booking.seats, zone.capacity)
    zone.save(update_fields=['free_seats'])


@transaction.atomic
def review_chill_booking(booking_id, actor, action, identity_confirmed=False):
    booking = ChillZoneBookings.objects.select_for_update().get(pk=booking_id)
    if booking.status != ChillZoneBookings.Status.PENDING:
        raise ValidationError(f'Booking is already {booking.status}.')
    if action == 'confirm':
        if not identity_confirmed:
            raise ValidationError({'identity_confirmed': 'Confirm the client identity first.'})
        booking.status = ChillZoneBookings.Status.CONFIRMED
    else:
        _release_zone_seats(booking)
        booking.status = ChillZoneBookings.Status.REJECTED
    booking.reviewed_by = actor
    booking.reviewed_at = timezone.now()
    booking.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])
    return booking


@transaction.atomic
def cancel_chill_booking(booking_id, actor):
    booking = ChillZoneBookings.objects.select_for_update().get(pk=booking_id)
    if booking.user_id != actor.id and not actor.is_superuser:
        raise PermissionDenied('You can cancel only your own booking.')
    if booking.status != ChillZoneBookings.Status.PENDING:
        raise ValidationError(f'Booking is already {booking.status}.')
    _release_zone_seats(booking)
    booking.status = ChillZoneBookings.Status.CANCELLED
    booking.save(update_fields=['status'])
    return booking

@transaction.atomic
def create_chill_order(cashier, booking, items, payment_type):
    booking = ChillZoneBookings.objects.select_for_update().get(pk=booking.pk)
    if booking.status != ChillZoneBookings.Status.CONFIRMED:
        raise ValidationError('Products can be sold only for a confirmed booking.')

    lines = {}
    for item in items:
        product = item['product']
        if not product.is_active:
            raise ValidationError(f'Product "{product.name}" is not available.')
        entry = lines.setdefault(product.id, {'product': product, 'quantity': 0})
        entry['quantity'] += item['quantity']

    total = sum((l['product'].price * l['quantity'] for l in lines.values()), Decimal('0.00'))
    payment = Payment.objects.create(price=total, is_success=True, payment_type=payment_type)
    order = ChillZoneOrder.objects.create(booking=booking, cashier=cashier, payment=payment, total_price=total)
    ChillZoneOrderItem.objects.bulk_create([
        ChillZoneOrderItem(order=order, product=l['product'], quantity=l['quantity'], unit_price=l['product'].price)
        for l in lines.values()])
    return order