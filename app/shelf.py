from django.db import IntegrityError, transaction
from django.db.models import Count
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from xml.sax.saxutils import escape

from app.models import ShelfItem, ShelfSettings

Status = ShelfItem.Status
Visibility = ShelfSettings.Visibility

FEATURED_LIMIT = 4
VISIBILITY_FIELD = {
    Status.TO_READ: 'to_read_visibility',
    Status.CURRENTLY_READING: 'currently_reading_visibility',
    Status.READ: 'read_visibility',}
ORDER = [Status.TO_READ, Status.CURRENTLY_READING, Status.READ]


def get_settings(user):
    return ShelfSettings.objects.get_or_create(user=user)[0]


def visible_statuses(settings):
    return [s for s in ORDER if getattr(settings, VISIBILITY_FIELD[s]) == Visibility.EVERYONE]


def share_enabled(settings):
    return bool(visible_statuses(settings))

def _check_finish_date(status, finished_at):
    if status != Status.READ:
        if finished_at is not None:
            raise ValidationError({'finished_at': 'The finish date is only for the "Read" list.'})
        return
    if finished_at is not None and finished_at > timezone.localdate():
        raise ValidationError({'finished_at': 'The finish date cannot be in the future.'})


@transaction.atomic
def add_or_move(user, book, status, finished_at=None):
    _check_finish_date(status, finished_at)
    item = ShelfItem.objects.select_for_update().filter(user=user, book=book).first()
    if item is None:
        try:
            with transaction.atomic():
                item = ShelfItem.objects.create(
                    user=user, book=book, status=status,
                    finished_at=(finished_at or timezone.localdate()) if status == Status.READ else None)
            return item, True
        except IntegrityError:
            item = ShelfItem.objects.select_for_update().get(user=user, book=book)
    if item.status != status:
        item.status = status
        item.added_at = timezone.now()
        if status != Status.CURRENTLY_READING:
            item.show_in_profile = False
    if status == Status.READ:
        item.finished_at = finished_at or item.finished_at or timezone.localdate()
    else:
        item.finished_at = None
    item.save()
    return item, False


def update_item(user, item, status=None, finished_at=None):
    return add_or_move(user, item.book, status or item.status, finished_at)[0]


@transaction.atomic
def set_featured(user, item_id, value):
    item = ShelfItem.objects.select_for_update().filter(pk=item_id, user=user).first()
    if item is None:
        raise ValidationError('Shelf item not found.')
    if value:
        if item.status != Status.CURRENTLY_READING:
            raise ValidationError('Only books from "Currently reading" can be shown in the profile.')
        featured = ShelfItem.objects.select_for_update().filter(user=user, show_in_profile=True)
        if not item.show_in_profile and featured.count() >= FEATURED_LIMIT:
            raise ValidationError(f'You can show up to {FEATURED_LIMIT} books in the profile.')
    item.show_in_profile = value
    item.save(update_fields=['show_in_profile'])
    return item

def filtered_items(user, params, status=None):
    qs = (ShelfItem.objects.filter(user=user)
          .select_related('book').prefetch_related('book__author'))
    status = status or params.get('status')
    if status:
        if status not in Status.values:
            raise ValidationError({'status': f'Unknown list "{status}".'})
        qs = qs.filter(status=status)
    if params.get('search'):
        qs = qs.filter(book__name__icontains=params['search'])
    return qs.order_by('added_at' if params.get('ordering') == 'added_at' else '-added_at', 'id')


def counts(user):
    raw = dict(ShelfItem.objects.filter(user=user).values_list('status').annotate(n=Count('id')))
    return {s.value: raw.get(s.value, 0) for s in ORDER}


def featured_books(user):
    return (ShelfItem.objects.filter(user=user, show_in_profile=True, status=Status.CURRENTLY_READING)
            .select_related('book').prefetch_related('book__author').order_by('-added_at'))


def display_name(user):
    return user.name or user.username


def build_share_svg(user, settings, per_list=5):
    shown = visible_statuses(settings)
    totals = counts(user)
    width, y = 640, 90
    parts = []
    for status in shown:
        titles = list(ShelfItem.objects.filter(user=user, status=status)
                      .select_related('book').order_by('-added_at').values_list('book__name', flat=True)[:per_list])
        parts.append(f'<text x="32" y="{y}" font-size="20" font-weight="700" fill="#2b2b2b">'
                     f'{escape(Status(status).label)} ({totals[status]})</text>')
        y += 30
        for title in titles:
            parts.append(f'<text x="48" y="{y}" font-size="16" fill="#444">{escape(title)}</text>')
            y += 26
        if totals[status] > len(titles):
            parts.append(f'<text x="48" y="{y}" font-size="14" fill="#888">+{totals[status] - len(titles)} more</text>')
            y += 26
        y += 18
    height = y + 20
    title = escape(f"{display_name(user)}'s shelf")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
            f'font-family="Arial, Helvetica, sans-serif">'
            f'<rect width="100%" height="100%" rx="16" fill="#fbf6ec"/>'
            f'<text x="32" y="52" font-size="26" font-weight="700" fill="#7a4b1e">{title}</text>'
            + ''.join(parts) + '</svg>')