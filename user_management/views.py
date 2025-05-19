from datetime import datetime, timezone
from django.db.models import OuterRef, Subquery, IntegerField, Value, When, Case
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import logout
from status_maintain.utility import UserType, AttendanceStatus
from .models import Attendance, User, UserProfile
from .serializers import (RegisterSerializer, LoginSerializer, UserSerializer, UserProfileSerializer,
                          AttendanceSerializer, AutoCloseAttendanceSerializer, LogoutSerializer, OpenShopSerializer)
from drf_spectacular.utils import extend_schema
from rest_framework.generics import GenericAPIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone as tz


class IsVendor(IsAuthenticated):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.user_type == UserType.VENDOR.CODE


class RegisterView(GenericAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    @extend_schema(request=RegisterSerializer)
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "User registered successfully"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(GenericAPIView):
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]

    @extend_schema(request=LoginSerializer)
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            refresh = RefreshToken.for_user(user)
            return Response({
                "message": "Logged in successfully",
                "access": str(refresh.access_token),
                "refresh": str(refresh)
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(GenericAPIView):
    serializer_class = LogoutSerializer

    def get(self, request):
        logout(request)
        serializer = self.get_serializer()
        return Response(serializer.data, status=status.HTTP_200_OK)

class UserProfileAPIView(GenericAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        return profile

    @extend_schema(responses={200: UserProfileSerializer})
    def get(self, request):
        profile = self.get_object()
        serializer = self.get_serializer(profile, context={'request': request})
        return Response(serializer.data)

    @extend_schema(request=UserProfileSerializer, responses={200: UserProfileSerializer})
    def put(self, request):
        profile = self.get_object()
        serializer = self.get_serializer(profile, data=request.data, partial=False, context={'request': request})
        if serializer.is_valid():
            serializer.save(modifed_by=request.user.id, modified_on=datetime.now(timezone.utc))
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(request=UserProfileSerializer, responses={200: UserProfileSerializer})
    def patch(self, request):
        profile = self.get_object()
        serializer = self.get_serializer(profile, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save(modifed_by=request.user.id, modified_on=datetime.now(timezone.utc))
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MarkAttendanceAPIView(GenericAPIView):
    serializer_class = AttendanceSerializer
    permission_classes = [IsVendor]

    @extend_schema(request=AttendanceSerializer, responses={201: AttendanceSerializer})
    def post(self, request):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            today = tz.now().date()
            status_code = serializer.validated_data['status']

            attendance, created = Attendance.objects.update_or_create(
                vendor=request.user,
                date=today,
                defaults={
                    'status': status_code,
                    'created_by': request.user.id
                }
            )

            if status_code == AttendanceStatus.OPEN.CODE:
                request.user.is_available_today = True
            elif status_code == AttendanceStatus.CLOSED.CODE:
                request.user.is_available_today = False

            request.user.save(update_fields=['is_available_today'])

            response_serializer = self.get_serializer(attendance)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class OpenShopsAPIView(GenericAPIView):
    serializer_class = OpenShopSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: OpenShopSerializer(many=True)})
    def get(self, _request):
        today = tz.now().date()

        latest_attendance_subquery = Attendance.objects.filter(
            vendor=OuterRef('pk'),
            date=today
        ).order_by('-timestamp')

        all_vendors = User.objects.filter(
            user_type=UserType.VENDOR.CODE,
            is_active=True,
            is_deleted=False,
        ).annotate(
            latest_status=Subquery(latest_attendance_subquery.values('status')[:1])
        ).annotate(
            sort_order=Case(
                When(latest_status=AttendanceStatus.OPEN.CODE, then=Value(0)),
                When(latest_status=AttendanceStatus.CLOSED.CODE, then=Value(1)),
                default=Value(2),
                output_field=IntegerField()
            )
        ).order_by('sort_order', 'first_name')

        serializer = self.get_serializer(all_vendors, many=True)
        return Response(serializer.data)


class AttendanceGraphDataAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: None})
    def get(self, request):
        attendances = Attendance.objects.filter(vendor=request.user).order_by('date')
        data = {
            'labels': [att.date.strftime('%Y-%m-%d') for att in attendances],
            'open_counts': [1 if att.status == AttendanceStatus.OPEN.CODE else 0 for att in attendances],
            'closed_counts': [1 if att.status == AttendanceStatus.CLOSED.CODE else 0 for att in attendances],
        }
        return Response(data)


class AutoCloseAttendanceAPIView(GenericAPIView):
    serializer_class = AutoCloseAttendanceSerializer
    permission_classes = [AllowAny]

    def get(self, _request):
        now_time = tz.now().time()
        vendors = User.objects.filter(user_type=UserType.VENDOR.CODE, is_available_today=True)

        for vendor in vendors:
            profile = vendor.profile
            if profile.closing_time and now_time >= profile.closing_time:
                latest_attendance = Attendance.objects.filter(
                    vendor=vendor, date=tz.now().date()
                ).order_by('-timestamp').first()

                if latest_attendance and latest_attendance.status != AttendanceStatus.CLOSED.CODE:
                    Attendance.objects.create(
                        vendor=vendor,
                        status=AttendanceStatus.CLOSED.CODE,
                        created_by=vendor.id
                    )
                    vendor.is_available_today = False
                    vendor.save(update_fields=['is_available_today'])

        serializer = self.get_serializer({'message': 'Auto close attendance done'})
        return Response(serializer.data)
