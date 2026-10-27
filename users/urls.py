from django.urls import path
from rest_framework.routers import DefaultRouter
from users.views import EmployeeViewSet, RegisterView, LoginView, UserViewSet, GroupViewSet, VerifyEmailView, \
    ResetPassword, PasswordResetConfirm

router = DefaultRouter()
router.register('employees', EmployeeViewSet)
router.register('users',UserViewSet)
router.register('groups', GroupViewSet, basename='groups')
urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('verify/<uidb64>/<token>/',VerifyEmailView.as_view(),name='verify-email'),
    path('reset-password/',ResetPassword.as_view(),name='reset-password'),
    path('reset-password/<uidb64>/<token>/',PasswordResetConfirm.as_view(),name='password-reset-confirm'),
] + router.urls