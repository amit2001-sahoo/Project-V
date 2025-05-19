from django.contrib.auth.base_user import BaseUserManager
from django.db import models
from django.contrib.auth.models import AbstractBaseUser

from status_maintain.utility import BaseUserModel


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        superuser = self.create_user(email, password, **extra_fields)
        UserProfile.objects.create(
            user=superuser,
            created_by=superuser.id,
            modified_by=superuser.id,
        )
        return superuser

    def get_by_natural_key(self, email):
        return self.get(email=email)


class User(AbstractBaseUser):
    username = None
    is_staff = None
    date_joined = None

    is_superuser = models.BooleanField(default=False, db_column='IS_SUPERUSER')
    email = models.EmailField(unique=True, db_column='EMAIL_ID')
    first_name = models.CharField(max_length=15, db_column='FIRST_NAME')
    last_name = models.CharField(max_length=15, null=True, db_column='LAST_NAME')
    password = models.TextField(null=True, blank=True, db_column='PASSWORD')
    phone_number = models.CharField(max_length=15, blank=True, null=True, db_column='PHONE_NUMBER')
    gender = models.CharField(max_length=10, blank=True, null=True, db_column='GENDER')
    business_name = models.CharField(max_length=100, blank=True, null=True, db_column='BUSINESS_NAME')
    is_available_today = models.BooleanField(default=False, db_column='IS_AVAILABLE_TODAY')
    is_active = models.BooleanField(default=True, db_column='IS_ACTIVE')
    is_deleted = models.BooleanField(default=False, db_column='IS_DELETED')
    last_login = models.DateTimeField(null=True, blank=True, db_column='LAST_LOGIN')
    user_type = models.PositiveIntegerField(null=True, blank=True, db_column='USER_TYPE')
    created_on = models.DateTimeField(auto_now_add=True, db_column='CREATED_ON')
    created_by = models.PositiveIntegerField(null=True, blank=True, db_column='CREATED_BY')
    modified_on = models.DateTimeField(null=True, db_column='MODIFIED_ON')
    modified_by = models.PositiveIntegerField(null=True, blank=True, db_column='MODIFIED_BY')

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email

    class Meta:
        db_table = "USER"
        ordering = ['first_name']
        verbose_name = "User"
        verbose_name_plural = "Users"


class UserProfile(BaseUserModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile', db_column='USER_ID')
    address = models.TextField(blank=True, null=True, db_column='ADDRESS')
    shop_address = models.TextField(blank=True, null=True, db_column='SHOP_ADDRESS')
    shop_description = models.TextField(blank=True, null=True, db_column='SHOP_DESCRIPTION')
    profile_picture = models.CharField(max_length=500, blank=True, null=True, db_column='PROFILE_PICTURE')
    opening_time = models.TimeField(null=True, blank=True, db_column='OPENING_TIME')
    closing_time = models.TimeField(null=True, blank=True, db_column='CLOSING_TIME')

    class Meta:
        db_table = "USER_PROFILE"
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

class VendorShopImage(BaseUserModel):
    vendor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shop_images', db_column='VENDOR_ID')
    shop_image = models.CharField(max_length=500, blank=True, null=True, db_column='SHOP_IMAGE')

    class Meta:
        db_table = "VENDOR_SHOP_IMAGE"
        verbose_name = "Vendor Shop Image"
        verbose_name_plural = "Vendor Shop Images"

class Attendance(BaseUserModel):
    vendor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendances', db_column='VENDOR_ID')
    date = models.DateField(auto_now_add=True, db_column='DATE')
    status = models.PositiveIntegerField(db_column='ATTENDANCE_STATUS')
    timestamp = models.DateTimeField(auto_now_add=True, db_column='TIMESTAMP')

    class Meta:
        db_table = "ATTENDANCE"
        verbose_name = "Attendance"
        verbose_name_plural = "Attendances"
        unique_together = ('vendor', 'date', 'status')
