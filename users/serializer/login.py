from django.core.cache import cache
from django.contrib.auth import authenticate
from rest_framework import serializers

MAX_ATTEMPTS = 10
LOCKOUT_SECONDS = 5 * 60

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        request = self.context.get('request')
        ip = request.META.get('REMOTE_ADDR', 'unknown')
        cache_key = f'login_attempts:{data["username"]}:{ip}'

        attempts = cache.get(cache_key, 0)
        if attempts >= MAX_ATTEMPTS:
            raise serializers.ValidationError(
                'Too many failed attempts. Try again in 5 minutes. ≧ ﹏ ≦'
            )

        user = authenticate(request=request, username=data['username'], password=data['password'])

        if not user:
            cache.set(cache_key, attempts + 1, timeout=LOCKOUT_SECONDS)
            raise serializers.ValidationError('Invalid username or password. ＞﹏＜')
        cache.delete(cache_key)

        if not user.is_email_verified:
            raise serializers.ValidationError('Please verify your email before logging in.')

        data['user'] = user
        return data