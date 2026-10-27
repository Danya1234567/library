from django.db import transaction
from rest_framework import serializers
from users.models import Employee, User


class EmployeeClientSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='user.name', read_only=True)
    position = serializers.SlugRelatedField(slug_field='name_of_position', read_only=True)
    class Meta:
        model = Employee
        fields = ['id', 'name', 'position']

class EmployeeStaffSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='user.name', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    position = serializers.SlugRelatedField(slug_field='name_of_position', read_only=True)
    shift = serializers.SlugRelatedField(slug_field='name_of_shift', many=True, read_only=True)
    library = serializers.SlugRelatedField(slug_field='name', read_only=True)
    class Meta:
        model = Employee
        fields = ['id', 'name', 'username', 'age', 'salary', 'position', 'shift', 'library']


class EmployeeWriteSerializer(serializers.ModelSerializer):
    username = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)
    name = serializers.CharField(write_only=True)
    surname = serializers.CharField(write_only=True)
    phone_number = serializers.CharField(write_only=True)
    email = serializers.EmailField(write_only=True)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('Пользователь с таким username уже существует.')
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('Пользователь с таким email уже существует.')
        return value

    class Meta:
        model = Employee
        fields = [
            'id', 'username', 'password', 'name', 'surname', 'email', 'phone_number',
            'age', 'salary', 'position', 'shift', 'library',
        ]

    def create(self, validated_data):
        shift = validated_data.pop('shift', [])

        user_data = {
            'username': validated_data.pop('username'),
            'password': validated_data.pop('password'),
            'name': validated_data.pop('name'),
            'surname': validated_data.pop('surname'),
            'phone_number': validated_data.pop('phone_number'),
            'email': validated_data.pop('email'),
        }

        with transaction.atomic():
            user = User.objects.create_user(**user_data, is_staff=True)
            employee = Employee.objects.create(user=user, **validated_data)
            position = employee.position
            if position.default_group:
                user.groups.add(position.default_group)
            if shift:
                employee.shift.set(shift)

        return employee

class EmployeeUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = ['id', 'age', 'salary', 'position', 'shift', 'library']

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        if 'position' in validated_data:
            group = instance.position.default_group
            if group:
                instance.user.groups.set([group])
            else:
                instance.user.groups.clear()
        return instance
