from django.utils import timezone


def chill_zone_receipt_text(booking):
    zone=booking.chill_zone
    payment=booking.payment
    created=timezone.localtime(booking.created_at).strftime('%Y-%m-%d %H:%M')
    lines=[
        'CHILL ZONE RECEIPT',
        '='* 32,
        f'Order No: {booking.id}',
        f'Order Date: {created}',
        f'Branch: {zone.library.name} ({zone.branch})',
        f'Zone: {zone.name}',
        f'People (seats): {booking.seats}',
        f'Price per seats: {zone.price}',
        f'Total paid: {booking.total_price}',
        f'Payment Type: {payment.payment_type.name if payment else " - "}',
        f'Client: {booking.user.phone_number or booking.user.username}',
        '='*32,
        'Show this receipt to the librarian ^_^'
    ]
    return '\n'.join(lines) + '\n'

def chill_zone_product_receipt_text(order):
    booking = order.booking
    zone = booking.chill_zone
    created = timezone.localtime(order.created_at).strftime('%Y-%m-%d %H:%M')
    cashier = order.cashier.name or order.cashier.username if order.cashier else '-'
    lines = [
        'CHILL ZONE PRODUCTS RECEIPT',
        '=' * 32,
        f'Receipt No: {order.id}',
        f'Date: {created}',
        f'Branch: {zone.library.name} ({zone.branch})',
        f'Zone: {zone.name}',
        f'Booking Order No: {booking.id}',
        f'Client: {booking.user.phone_number or booking.user.username}',
        f'Cashier: {cashier}',
        '-' * 32,
    ]
    for item in order.items.select_related('product'):
        lines.append(f'{item.quantity} x {item.product.name}  {item.unit_price} = {item.unit_price * item.quantity}')
    lines += [
        '-' * 32,
        f'Total paid: {order.total_price}',
        f'Payment type: {order.payment.payment_type.name}',
        '=' * 32,
        'Thank you ^_^',
    ]
    return '\n'.join(lines) + '\n'