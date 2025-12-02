from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('sign-up', views.sign_up, name='sign_up'),
    path('book/<int:pitch_id>/', views.book_pitch, name='book_pitch'),
    path('pitches/', views.pitch_list, name='pitch_list'),
    path('facility/<int:facility_id>/', views.facility_detail, name='facility_detail'),

    # Admin booking management (custom dashboard)
    path('dashboard/bookings/', views.admin_booking_list, name='admin_booking_list'),
    path('dashboard/bookings/<int:booking_id>/update-status/', views.admin_update_booking_status,
         name='admin_update_booking_status'),
]
