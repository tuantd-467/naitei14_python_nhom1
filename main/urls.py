from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),  
    path('sign-up', views.signup, name='signup'),
    path(
        'activate/<str:token>/',
        views.activate_account,
        name='activate_account'),
    path('pitches/', views.pitch_list, name='pitch_list'),
    path(
        'facility/<int:facility_id>/',
        views.facility_detail,
        name='facility_detail'),
    path('favorites/', views.favorite_list, name='favorite_list'),
    path(
        'favorite/toggle/<int:pitch_id>/',
        views.toggle_favorite,
        name='toggle_favorite'),
    # Admin booking management (custom dashboard)
    path(
        'dashboard/bookings/',
        views.admin_booking_list,
        name='admin_booking_list'),
    path('dashboard/bookings/<int:booking_id>/update-status/', views.admin_update_booking_status,
         name='admin_update_booking_status'),
    # Admin pitch CRUD
    path('admin/pitches/', views.admin_pitch_list, name='admin_pitch_list'),
    path('admin/pitches/create/', views.admin_pitch_create, name='admin_pitch_create'),
    path('admin/pitches/<int:pitch_id>/edit/', views.admin_pitch_update, name='admin_pitch_update'),
    path('admin/pitches/<int:pitch_id>/delete/', views.admin_pitch_delete, name='admin_pitch_delete'),

    path(
        'book/<int:pitch_id>/',
        views.user_booking_create,
        name='user_booking_create'),
    path(
        'booking-history/',
        views.user_booking_list,
        name='user_booking_list'),
    path(
        'booking/<int:booking_id>/',
        views.user_booking_detail,
        name='user_booking_detail'),
    path(
        'booking/<int:booking_id>/cancel/',
        views.user_booking_cancel,
        name='user_booking_cancel'),

    # Admin Booking
    path(
        'admin/booking/<int:booking_id>/approve/',
        views.admin_booking_approve,
        name='admin_booking_approve'),
    path(
        'admin/booking/<int:booking_id>/reject/',
        views.admin_booking_reject,
        name='admin_booking_reject'),

    # AJAX
    path(
        'ajax/time-slots/<int:pitch_id>/',
        views.get_available_time_slots_ajax,
        name='ajax_time_slots'),
    path(
        'ajax/check-voucher/',
        views.check_voucher_ajax,
        name='ajax_check_voucher'),

    path('pitch/<int:pitch_id>/review/', views.add_review, name='add_review'),
]
