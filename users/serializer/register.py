from rest_framework import serializers
from users.models import User



class RegisterSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = [
            'name',
            'surname',
            'username',
            'phone_number',
            'password',
            'email'
        ]

        extra_kwargs = {
            'password': {
                'write_only': True
            }
        }

    def create(self, validated_data):
        return User.objects.create_user(**validated_data,is_active=False)