from django.contrib.auth.models import AbstractUser
from django.db import models

# Create your models here.

class User(AbstractUser):
    username = models.CharField(max_length=100, unique=True)
    email = models.EmailField(max_length=100, unique=True)
    email_verified_at=models.DateTimeField(blank=True, null=True)
    is_email_verified = models.BooleanField(default=False)
    name = models.CharField(max_length=100)
    surname = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=100)
    about_me = models.TextField(blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    link1 = models.URLField(blank=True,null=True)
    link2 = models.URLField(blank=True,null=True)
    link3 = models.URLField(blank=True,null=True)
    def __str__(self):
        return self.username

    class Meta:
        db_table = 'users'

class Employee(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee_profile')
    age = models.PositiveIntegerField(default=18)
    salary = models.DecimalField(max_digits=10, decimal_places=2)
    position = models.ForeignKey('app.Position', on_delete=models.CASCADE, related_name='employees')
    shift = models.ManyToManyField('app.Shift', blank=True, related_name='employees')
    library=models.ForeignKey('app.Library', on_delete=models.CASCADE, related_name='employees',null=True,blank=True)

    def __str__(self):
        return self.user.username

class PointTransaction(models.Model):
    class Reason(models.TextChoices):
        RETURN_GOOD='Return good','Book returned in good condition'
        RETURN_BAD='Return bad','Book returned in bad condition'
        OVERDUE='Overdue','Overdue returned'
        PURCHASE='Purchase','Book purchase'
        GOAL_ACHIEVED= 'Goal achieved', 'Goal achieved'
        QUESTIONNAIRE='questionnaire','Preference questionnaire'

    user=models.ForeignKey(User, on_delete=models.CASCADE, related_name='point_transactions')
    points=models.IntegerField(help_text='It could be negative(Penalties)')
    reason=models.CharField(max_length=30, choices=Reason.choices)
    source_key=models.CharField(max_length=50,help_text='Reason of начисления')
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering=['-created_at','-id']
        constraints=[models.UniqueConstraint(fields=['user','reason','source_key'],name='unique_points_per_event'),]

class UserBadge(models.Model):
    class Badge(models.TextChoices):
        FIRST_BOOK='first_book','First book'
        FIVE_IN_MONTH='five_books_in_a_month','Five books in month'
        RELIABLE='reliable','Reliable'
        GOAL_GETTER='goal_getter','Goal getter'
        EXPLORER='explorer','Explorer'
        NOTE_KEEPER='note_keeper','Note keeper'
        LOYAL_MEMBER='loyal_member','Loyal member'
        CHILL_ZONE_GUEST='chill_zone_guest','Chill zone guest'
    user=models.ForeignKey(User, on_delete=models.CASCADE, related_name='badges')
    badge=models.CharField(max_length=30,choices=Badge.choices)
    earned_at=models.DateTimeField(auto_now_add=True)
    class  Meta:
        ordering=['earned_at']
        constraints=[models.UniqueConstraint(fields=['user','badge'],name='unique_badge_per_user')]

class UserActivity(models.Model):
    class Type(models.TextChoices):
        GOAL_ACHIEVED = 'goal_achieved', 'Goal achieved'
        NOTE_CREATED = 'note_created', 'Note created'
    user=models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    type=models.CharField(max_length=30,choices=Type.choices)
    ref=models.CharField(max_length=50,help_text='client`s id or note')
    created_at=models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints=[models.UniqueConstraint(fields=['user','type','ref'],name='unique_user_activity')]