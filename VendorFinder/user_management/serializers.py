import os
from datetime import datetime
from uuid import uuid4

from django.contrib.auth import authenticate
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from status_maintain.utility import UserType, AttendanceStatus
from .models import User, Attendance, UserProfile, VendorShopImage
from .storage import AzureBlobStorage


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    address = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    shop_address = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    shop_description = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    profile_picture = serializers.CharField(max_length=500, required=False, allow_null=True, allow_blank=True)
    opening_time = serializers.TimeField(required=False, allow_null=True)
    closing_time = serializers.TimeField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = (
        'email', 'first_name', 'last_name', 'password', 'phone_number', 'business_name', 'user_type', 'gender',
        'address', 'shop_address', 'shop_description', 'profile_picture', 'opening_time', 'closing_time')

    def validate(self, data):
        if data.get('user_type') != UserType.VENDOR.CODE:
            for field in ['business_name', 'shop_address', 'shop_description']:
                if data.get(field):
                    raise serializers.ValidationError(f"Only vendors can set {field}.")
        opening = data.get("opening_time")
        closing = data.get("closing_time")
        if opening and closing and closing <= opening:
            raise serializers.ValidationError("Closing time must be after opening time.")

        return data

    def create(self, validated_data):
        profile_data = {
            'address': validated_data.pop('address', None),
            'shop_address': validated_data.pop('shop_address', None),
            'shop_description': validated_data.pop('shop_description', None),
            'profile_picture': validated_data.pop('profile_picture', None),
        }
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()

        UserProfile.objects.create(user=user, **{k: v for k, v in profile_data.items() if v is not None})
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data.get('email')
        password = data.get('password')
        user = authenticate(email=email, password=password)
        if user and user.is_active:
            return {'user': user}
        raise serializers.ValidationError("Invalid credentials")


class UserSerializer(serializers.ModelSerializer):
    user_type = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'phone_number', 'business_name', 'user_type')
        read_only_fields = ('email', 'user_type')

    @extend_schema_field(serializers.CharField())
    def get_user_type(self, obj):
        if obj.user_type:
            return UserType.get_enum_name(obj.user_type)
        return None

class UserProfileSerializer(serializers.ModelSerializer):
    shop_images = serializers.ListField(
        child=serializers.FileField(), required=False, allow_empty=True
    )
    profile_picture = serializers.FileField(required=False, allow_null=True, allow_empty_file=True)
    first_name = serializers.CharField(max_length=15, required=False, allow_null=True, allow_blank=True)
    last_name = serializers.CharField(max_length=15, required=False, allow_null=True, allow_blank=True)
    phone_number = serializers.CharField(max_length=15, required=False, allow_null=True, allow_blank=True)
    business_name = serializers.CharField(max_length=100, required=False, allow_null=True, allow_blank=True)
    gender = serializers.CharField(max_length=50, required=False, allow_null=True, allow_blank=True)
    opening_time = serializers.TimeField(allow_null=True,required=False)
    closing_time = serializers.TimeField(allow_null=True,required=False)

    class Meta:
        model = UserProfile
        fields = (
            'id', 'first_name', 'last_name', 'phone_number', 'business_name', 'gender',
            'address', 'shop_address', 'shop_description',
            'profile_picture','shop_images', 'opening_time', 'closing_time',
            'created_on', 'created_by', 'modified_on', 'modified_by'
        )
        read_only_fields = ('id', 'created_on', 'created_by', 'modified_on', 'modified_by')

    def validate(self, data):
        user = self.context['request'].user
        if user.user_type != UserType.VENDOR.CODE:
            for field in ['business_name', 'shop_address', 'shop_description']:
                if field in data and data[field]:
                    raise serializers.ValidationError(f"Only vendors can set {field}.")

        opening = data.get("opening_time")
        closing = data.get("closing_time")
        if opening and closing and closing <= opening:
            raise serializers.ValidationError("Closing time must be after opening time.")

        return data

    @staticmethod
    def _generate_file_name(file_name, unique_suffix):
        current_datetime = datetime.now()
        datetime_string = current_datetime.strftime("%Y%m%d_%H%M%S")
        _, file_extension = os.path.splitext(file_name)
        return f"{datetime_string}_{unique_suffix}{file_extension.lower()}"

    def upload_profile_in_blob(self, uploaded_file, file_name):
        new_file_name = self._generate_file_name(file_name, uuid4())
        blob_path = f"user_profiles/{new_file_name}"
        azure_storage = AzureBlobStorage()
        file_data = uploaded_file.read()
        azure_storage.upload_file(file_content=file_data, blob_name=blob_path)
        return blob_path

    def upload_shop_image_in_blob(self, uploaded_file, file_name, index):
        new_file_name = self._generate_file_name(file_name, f"{uuid4()}_{index}")
        blob_path = f"shop_images/{new_file_name}"
        azure_storage = AzureBlobStorage()
        file_data = uploaded_file.read()
        azure_storage.upload_file(file_content=file_data, blob_name=blob_path)
        return blob_path

    def update(self, instance, validated_data):
        user_data = {key: validated_data.pop(key) for key in [
            'first_name', 'last_name', 'phone_number', 'business_name', 'gender'
        ] if key in validated_data}

        user = instance.user
        for attr, value in user_data.items():
            setattr(user, attr, value)
        user.save()

        uploaded_profile = validated_data.pop('profile_picture', None)
        if uploaded_profile:
            path = self.upload_profile_in_blob(uploaded_profile, uploaded_profile.name)
            instance.profile_picture = path

        uploaded_shop_images = validated_data.pop('shop_images', None)
        if uploaded_shop_images is not None:
            VendorShopImage.objects.filter(vendor=user).delete()

            for idx, image in enumerate(uploaded_shop_images):
                path = self.upload_shop_image_in_blob(image, image.name, idx)
                VendorShopImage.objects.create(vendor=user, shop_image=path)

        for field in ['opening_time', 'closing_time']:
            if field in validated_data and not validated_data[field]:
                validated_data[field] = getattr(instance, field)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance

class UserProfileReadSerializer(serializers.ModelSerializer):
    shop_images = serializers.SerializerMethodField()
    profile_picture = serializers.SerializerMethodField()
    first_name = serializers.CharField(source='user.first_name')
    last_name = serializers.CharField(source='user.last_name')
    phone_number = serializers.CharField(source='user.phone_number')
    business_name = serializers.CharField(source='user.business_name')
    gender = serializers.CharField(source='user.gender')

    class Meta:
        model = UserProfile
        fields = (
            'id', 'first_name', 'last_name', 'phone_number', 'business_name', 'gender',
            'address', 'shop_address', 'shop_description',
            'profile_picture','shop_images', 'opening_time', 'closing_time',
            'created_on', 'created_by', 'modified_on', 'modified_by'
        )

    @extend_schema_field(serializers.URLField())
    def get_profile_picture(self, obj):
        if obj.profile_picture:
            azure_storage = AzureBlobStorage()
            return azure_storage.get_file_url(blob_name=obj.profile_picture)
        return None

    @extend_schema_field(serializers.ListField(child=serializers.URLField()))
    def get_shop_images(self, obj):
        azure_storage = AzureBlobStorage()
        shop_images = obj.user.shop_images.all()
        return [
            azure_storage.get_file_url(blob_name=image.shop_image)
            for image in shop_images if image.shop_image
        ]

class AttendanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attendance
        fields = (
        'id', 'vendor', 'date', 'status', 'timestamp', 'created_on', 'created_by', 'modified_on', 'modified_by')
        read_only_fields = (
        'id', 'vendor', 'date', 'timestamp', 'created_on', 'created_by', 'modified_on', 'modified_by')

    @staticmethod
    def validate_status(value):
        valid_status = [item.CODE for item in AttendanceStatus]
        if value not in valid_status:
            raise serializers.ValidationError(
                f"Invalid attendance status. Allowed statuses are: {valid_status}"
            )
        return value

    def validate(self, data):
        vendor = self.context['request'].user
        date = data.get('date', self.instance.date if self.instance else None)
        status = data.get('status')
        if Attendance.objects.filter(vendor=vendor, date=date, status=status).exists():
            raise serializers.ValidationError(f"Attendance with status {status} already marked for today.")
        return data

    def create(self, validated_data):
        attendance = super().create(validated_data)
        user = attendance.vendor

        if attendance.status == AttendanceStatus.OPEN.CODE:
            user.is_available_today = True
        elif attendance.status == AttendanceStatus.CLOSED.CODE:
            user.is_available_today = False

        user.save(update_fields=["is_available_today"])
        return attendance


class OpenShopSerializer(serializers.ModelSerializer):
    shop_address = serializers.CharField(source='profile.shop_address', read_only=True)
    shop_description = serializers.CharField(source='profile.shop_description', read_only=True)
    opening_time = serializers.TimeField(source='profile.opening_time', read_only=True)
    closing_time = serializers.TimeField(source='profile.closing_time', read_only=True)
    attendance_status = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'email', 'first_name', 'last_name', 'phone_number',
            'business_name', 'gender', 'is_available_today',
            'shop_address', 'shop_description', 'opening_time', 'closing_time',
            'attendance_status'
        )

    @extend_schema_field(serializers.CharField())
    def get_attendance_status(self, obj):
        status_code = getattr(obj, 'latest_status', None)
        if status_code is not None:
            return AttendanceStatus.get_enum_name(status_code)
        return "No Attendance"

class AutoCloseAttendanceSerializer(serializers.Serializer):
    message = serializers.CharField()

class LogoutSerializer(serializers.Serializer):
    message = serializers.CharField(read_only=True, default="Logout successful.")