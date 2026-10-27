from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone

from app.models import (ChillZoneBookings, Notification, RentalItem, Subscription,)
from users.models import PointTransaction, UserBadge, UserActivity

Reason = PointTransaction.Reason
Badge = UserBadge.Badge

POINTS_RETURN_GOOD = 2
POINTS_RETURN_BAD = -5
POINTS_PER_OVERDUE_DAY = -5
POINTS_PER_PURCHASED_BOOK = 10
POINTS_GOAL_ACHIEVED = 5
POINTS_QUESTIONNAIRE = 10

LEVELS = [
    (300, 'library_friend', 'Library friend'),
    (150, 'scholar', 'Scholar'),
    (50, 'reader', 'Reader'),
    (0, 'new_reader', 'New reader'),
]

BADGE_DESCRIPTIONS = {
    Badge.FIRST_BOOK: 'Read and return your first book.',
    Badge.FIVE_IN_MONTH: 'Read 5 books within one month.',
    Badge.RELIABLE: 'Return 5 rented books in a row on time.',
    Badge.GOAL_GETTER: 'Set and achieve 3 goals.',
    Badge.EXPLORER: 'Read books from 3 different genres.',
    Badge.NOTE_KEEPER: 'Create 10 notes.',
    Badge.LOYAL_MEMBER: 'Take or renew a subscription 3 months in a row.',
    Badge.CHILL_ZONE_GUEST: 'Book chill zone seats 4 times within one month.',
}


def award(user, reason, points, source_key):
    if points == 0:
        return None
    obj, created = PointTransaction.objects.get_or_create(
        user=user, reason=reason, source_key=str(source_key), defaults={'points': points})
    return obj if created else None


def total_points(user):
    return PointTransaction.objects.filter(user=user).aggregate(t=Sum('points'))['t'] or 0


def get_level(total):
    for minimum, code, label in LEVELS:
        if total >= minimum:
            return {'code': code, 'label': label, 'min_points': minimum}
    return {'code': 'new_reader', 'label': 'New reader', 'min_points': 0}


def next_level(total):
    for minimum, code, label in reversed(LEVELS):
        if minimum > total:
            return {'code': code, 'label': label, 'min_points': minimum}
    return None


def points_summary(user):
    total = total_points(user)
    level, nxt = get_level(total), next_level(total)
    return {
        'total_points': total,
        'level': level['code'],
        'level_label': level['label'],
        'next_level': nxt['label'] if nxt else None,
        'points_to_next_level': nxt['min_points'] - total if nxt else 0,
    }


def on_book_returned(item):
    user, rental = item.rental.user, item.rental
    key = f'rental_item:{item.id}'
    if item.return_condition == RentalItem.Condition.BAD:
        award(user, Reason.RETURN_BAD, POINTS_RETURN_BAD, key)
    else:
        award(user, Reason.RETURN_GOOD, POINTS_RETURN_GOOD, key)
    days_late = (item.returned_at - rental.until).days
    if days_late > 0:
        award(user, Reason.OVERDUE, POINTS_PER_OVERDUE_DAY * days_late, key)
    evaluate_badges(user)


def on_books_purchased(order):
    for line in order.items.all():
        award(order.user, Reason.PURCHASE, POINTS_PER_PURCHASED_BOOK * line.quantity, f'order_item:{line.id}')
    evaluate_badges(order.user)


def on_chill_booked(booking):
    evaluate_badges(booking.user)


def on_goal_achieved(user, goal_id):
    UserActivity.objects.get_or_create(user=user, kind=UserActivity.Kind.GOAL_ACHIEVED, ref=str(goal_id))
    award(user, Reason.GOAL_ACHIEVED, POINTS_GOAL_ACHIEVED, f'goal:{goal_id}')
    evaluate_badges(user)


def on_note_created(user, note_id):
    UserActivity.objects.get_or_create(user=user, kind=UserActivity.Kind.NOTE_CREATED, ref=str(note_id))
    evaluate_badges(user)


def on_questionnaire_filled(user):
    award(user, Reason.QUESTIONNAIRE, POINTS_QUESTIONNAIRE, 'once')


def _has_window(dates, count, days=30):
    dates = sorted(dates)
    return any((dates[i + count - 1] - dates[i]).days <= days for i in range(len(dates) - count + 1))


def _returned_items(user):
    return (RentalItem.objects.filter(rental__user=user, returned_at__isnull=False)
            .select_related('rental').order_by('returned_at', 'id'))


def _first_book(user):
    return _returned_items(user).exists()


def _five_in_month(user):
    return _has_window([i.returned_at for i in _returned_items(user)], 5)


def _reliable(user):
    streak = 0
    for item in _returned_items(user):
        streak = streak + 1 if item.returned_at <= item.rental.until else 0
        if streak >= 5:
            return True
    return False


def _goal_getter(user):
    return UserActivity.objects.filter(user=user, kind=UserActivity.Kind.GOAL_ACHIEVED).count() >= 3


def _explorer(user):
    genres = (RentalItem.objects.filter(rental__user=user, returned_at__isnull=False)
              .exclude(book__genre__isnull=True).values('book__genre').distinct().count())
    return genres >= 3


def _note_keeper(user):
    return UserActivity.objects.filter(user=user, kind=UserActivity.Kind.NOTE_CREATED).count() >= 10


def _loyal_member(user):
    subs = Subscription.objects.filter(user=user).exclude(status='Cancelled').order_by('start_date')
    run, prev_end = 0, None
    for sub in subs:
        run = run + 1 if prev_end is not None and sub.start_date <= prev_end + timedelta(days=1) else 1
        prev_end = sub.end_date
        if run >= 3:
            return True
    return False


def _chill_zone_guest(user):
    active = [ChillZoneBookings.Status.PENDING, ChillZoneBookings.Status.CONFIRMED]
    created = ChillZoneBookings.objects.filter(user=user, status__in=active).values_list('created_at', flat=True)
    return _has_window([timezone.localtime(c).date() for c in created], 4)


BADGE_CHECKS = {
    Badge.FIRST_BOOK: _first_book,
    Badge.FIVE_IN_MONTH: _five_in_month,
    Badge.RELIABLE: _reliable,
    Badge.GOAL_GETTER: _goal_getter,
    Badge.EXPLORER: _explorer,
    Badge.NOTE_KEEPER: _note_keeper,
    Badge.LOYAL_MEMBER: _loyal_member,
    Badge.CHILL_ZONE_GUEST: _chill_zone_guest,
}


def evaluate_badges(user):
    owned = set(UserBadge.objects.filter(user=user).values_list('badge', flat=True))
    new = []
    for code, check in BADGE_CHECKS.items():
        if code in owned or not check(user):
            continue
        _, created = UserBadge.objects.get_or_create(user=user, badge=code)
        if created:
            new.append(code)
            Notification.objects.create(user=user, title='New badge',
                                        message=f'You earned the "{Badge(code).label}" badge!')
    return new