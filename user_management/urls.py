from django.urls import path
from . import views

urlpatterns = [
    path('v1/register', views.RegisterView.as_view(), name='register'),
    path('v1/login', views.LoginView.as_view(), name='login'),
    path('v1/logout', views.LogoutView.as_view(), name='logout'),

    path('v1/attendance/mark', views.MarkAttendanceAPIView.as_view(), name='mark_attendance'),
    path('v1/profile', views.UserProfileAPIView.as_view(), name='user_profile'),
    path('v1/shops/open', views.OpenShopsAPIView.as_view(), name='open_shops'),
    path('v1/attendance/graph-data', views.AttendanceGraphDataAPIView.as_view(), name='attendance_graph_data'),
    path('v1/auto-close-attendance', views.AutoCloseAttendanceAPIView.as_view(), name='auto-close-attendance'),

]
