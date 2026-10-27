import token

from django.views.generic import detail
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from django.contrib.auth.models import Group
from rest_framework import serializers, status
from rest_framework_simplejwt.tokens import RefreshToken
from app.pagination import Pagination
from users.models import Employee, User
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import  urlsafe_base64_decode,urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.core.mail import send_mail

from users.serializer.employee import EmployeeWriteSerializer, EmployeeUpdateSerializer, EmployeeClientSerializer, \
    EmployeeStaffSerializer
from users.serializer.login import LoginSerializer
from users.serializer.register import RegisterSerializer
from users.serializer.user import GroupSerializer, UserSerializer


# Create your views here.

class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        refresh = RefreshToken.for_user(user)

        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': {
                'id': user.id,
                'username': user.username,
                'name': user.name,
                'surname': user.surname,
                'email': user.email,
                'phone_number': user.phone_number,
                'is_staff': user.is_staff,
                'is_superuser': user.is_superuser,
                'groups': list(user.groups.values_list('name', flat=True)),
                'permissions': list(user.get_all_permissions()),
            },
        })

class RegisterView(CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def perform_create(self, serializer):
        user = serializer.save()
        uid = urlsafe_base64_encode(
            force_bytes(user.pk)
        )
        token = default_token_generator.make_token(user)
        verification_url = (
            f"http://localhost:5173/verify-email/{uid}/{token}/"
        )
        send_mail(
            subject='Подтверждение электронной почты',
            message=(
                f'Здравствуйте, {user.username}!\n\n'
                f'Спасибо за регистрацию. >_<\n\n'
                f'Для подтверждения вашей электронной почты '
                f'перейдите по ссылке:\n\n'
                f'{verification_url}\n\n'
                f'Если вы не регистрировались на нашем сайте, '
                f'просто проигнорируйте это письмо.'
            ),
            from_email=None,
            recipient_list=[user.email],
            fail_silently=False,
        )



class VerifyEmailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, uidb64, token):

        try:
            uid = urlsafe_base64_decode(uidb64).decode()
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response(
                {'error': 'Неверная ссылка подтверждения'},
                status=400
            )

        if user.is_email_verified:
            return Response({
                'message': 'Email уже подтверждён'
            })

        if default_token_generator.check_token(user, token):

            user.is_email_verified = True
            user.save(update_fields=['is_email_verified'])

            return Response({
                'message': 'Email успешно подтверждён'
            })

        return Response(
            {'error': 'Ссылка недействительна или устарела'},
            status=400
        )



class GroupViewSet(ReadOnlyModelViewSet):
    queryset = Group.objects.prefetch_related('permissions').order_by('name')
    serializer_class = GroupSerializer
    permission_classes = [IsAdminUser]

class EmployeeViewSet(ModelViewSet):
    queryset = Employee.objects.select_related('user', 'position', 'library').prefetch_related('shift')
    pagination_class = Pagination

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return EmployeeWriteSerializer
        if self.request.method in ('PUT', 'PATCH'):
            return EmployeeUpdateSerializer
        if self.request.user.is_staff:
            return EmployeeStaffSerializer
        return EmployeeClientSerializer

    def get_permissions(self):
        if self.request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            return [IsAdminUser()]
        return [IsAuthenticated()]

class UserViewSet(ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    pagination_class = Pagination
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_superuser or self.request.user.is_staff:
            qs = User.objects.all().order_by('username')
            search = self.request.query_params.get('search')
            if search:
                from django.db.models import Q
                qs = qs.filter(
                    Q(username__icontains=search) |
                    Q(name__icontains=search) |
                    Q(surname__icontains=search) |
                    Q(phone_number__icontains=search)
                )
            return qs
        return User.objects.filter(pk=self.request.user.pk)

class ResetPassword(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response( {'detail':'Email is not indicated'},status=status.HTTP_400_BAD_REQUEST)
        user = User.objects.filter(email=email).first()
        if not user:
            return Response({detail:'User with this email does not exist'},status=status.HTTP_404_NOT_FOUND)

        uid=urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        reset_link = (
            f'http://localhost:5173/reset-password/{uid}/{token}/'
        )
        send_mail(
            'Сброс пароля',
            f'Здравствуйте, {user.username}!\n\n'
            f'Для сброса пароля перейдите по ссылке:\n\n'
            f'{reset_link}',
            None,
            [user.email],
            fail_silently=False
        )
        return Response({'detail':'The link for resetting password is sent'})

class PasswordResetConfirm(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        password=request.data.get('password')
        if not password:
            return Response({'detail':'Password is not indicated'},status=status.HTTP_400_BAD_REQUEST)
        try:
            uid = urlsafe_base64_decode(force_bytes(request.user.pk)).decode()
            user=User.objects.get(pk=uid)
        except (ValueError,TypeError,OverflowError,User.DoesNotExist):
            return Response({'detail':'Not correct link for resetting password'},status=status.HTTP_400_BAD_REQUEST)
        if not default_token_generator.check_token(user,token):
            return Response({'detail':'Link not allowed'},status=status.HTTP_400_BAD_REQUEST)
        user.set_password(password)
        user.save()
        return Response({'detail':'Password has been reset'})