from rest_framework import serializers


from app.models import Book, ShelfItem, ShelfSettings


class ShelfBookSerializer(serializers.ModelSerializer):
    author = serializers.SlugRelatedField(many=True, slug_field='name', read_only=True)

    class Meta:
        model = Book
        fields = ['id', 'name', 'isbn', 'image_url', 'author']


class ShelfItemSerializer(serializers.ModelSerializer):
    book = ShelfBookSerializer(read_only=True)
    status_label = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = ShelfItem
        fields = ['id', 'book', 'status', 'status_label', 'added_at', 'finished_at', 'show_in_profile']


class ShelfAddSerializer(serializers.Serializer):
    book = serializers.PrimaryKeyRelatedField(queryset=Book.objects.all())
    status = serializers.ChoiceField(choices=ShelfItem.Status.choices)
    finished_at = serializers.DateField(required=False, allow_null=True)

    def create(self, validated_data):
        item, created = shelf.add_or_move(self.context['request'].user, validated_data['book'],validated_data['status'], validated_data.get('finished_at'))
        self.created = created
        return item


class ShelfUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=ShelfItem.Status.choices, required=False)
    finished_at = serializers.DateField(required=False, allow_null=True)


class ShelfSettingsSerializer(serializers.ModelSerializer):
    share_enabled = serializers.SerializerMethodField()
    class Meta:
        model = ShelfSettings
        fields = ['to_read_visibility', 'currently_reading_visibility', 'read_visibility', 'share_enabled']

    def get_share_enabled(self, obj):
        return shelf.share_enabled(obj)