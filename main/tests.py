from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.exceptions import ValidationError
from decimal import Decimal
from datetime import date, time, timedelta

from .models import (
    Facility, Pitch, PitchType, Favorite, TimeSlot, PitchTimeSlot,
    Voucher, Booking, BookingStatus
)
from . import constants

User = get_user_model()

# ===== Existing Tests =====
class FacilityDetailViewTest(TestCase):
    # ...existing code...
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            role=constants.ROLE_USER
        )
        
        self.pitch_type = PitchType.objects.create(
            name='Football',
            description='Football pitch'
        )
        
        self.facility = Facility.objects.create(
            name='Test Facility',
            address='123 Test St',
            phone='0123456789'
        )
        
        self.pitch1 = Pitch.objects.create(
            name='Pitch 1',
            facility=self.facility,
            pitch_type=self.pitch_type,
            base_price_per_hour=100.0,
            is_available=True
        )
        
        self.pitch2 = Pitch.objects.create(
            name='Pitch 2',
            facility=self.facility,
            pitch_type=self.pitch_type,
            base_price_per_hour=150.0,
            is_available=False
        )
        
        self.pitch3 = Pitch.objects.create(
            name='Pitch 3',
            facility=self.facility,
            pitch_type=self.pitch_type,
            base_price_per_hour=120.0,
            is_available=True
        )
    
    # ...existing code...
    def test_facility_detail_not_found(self):
        response = self.client.get(reverse('facility_detail', args=[9999]))
        self.assertEqual(response.status_code, 404)
    
    def test_facility_detail_filters_available_pitches(self):
        response = self.client.get(reverse('facility_detail', args=[self.facility.id]))
        self.assertEqual(response.status_code, 200)
        pitches = response.context['pitches']
        self.assertEqual(len(pitches), 2)
        pitch_ids = [p.id for p in pitches]
        self.assertIn(self.pitch1.id, pitch_ids)
        self.assertIn(self.pitch3.id, pitch_ids)
        self.assertNotIn(self.pitch2.id, pitch_ids)
    
    def test_facility_detail_unauthenticated_user_no_favorites(self):
        response = self.client.get(reverse('facility_detail', args=[self.facility.id]))
        self.assertEqual(response.status_code, 200)
        pitches = response.context['pitches']
        for pitch in pitches:
            self.assertFalse(pitch.is_favorited)
    
    def test_facility_detail_authenticated_user_with_favorites(self):
        Favorite.objects.create(user=self.user, pitch=self.pitch1)
        
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('facility_detail', args=[self.facility.id]))
        self.assertEqual(response.status_code, 200)
        
        pitches = {p.id: p for p in response.context['pitches']}
        self.assertTrue(pitches[self.pitch1.id].is_favorited)
        self.assertFalse(pitches[self.pitch3.id].is_favorited)
    
    def test_facility_detail_renders_correct_template(self):
        response = self.client.get(reverse('facility_detail', args=[self.facility.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'user/facility_detail.html')
    
    def test_facility_detail_context_contains_required_data(self):
        response = self.client.get(reverse('facility_detail', args=[self.facility.id]))
        context = response.context
        self.assertIn('facility', context)
        self.assertIn('pitches', context)
        self.assertIn('default_facility_image', context)
        self.assertIn('default_pitch_image', context)
        self.assertIn('is_user', context)
        self.assertEqual(context['facility'].id, self.facility.id)
    
    def test_facility_detail_is_user_flag_for_authenticated(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('facility_detail', args=[self.facility.id]))
        self.assertTrue(response.context['is_user'])
    
    def test_facility_detail_is_user_flag_for_unauthenticated(self):
        response = self.client.get(reverse('facility_detail', args=[self.facility.id]))
        self.assertFalse(response.context['is_user'])


# ===== TimeSlot Tests =====
class TimeSlotTests(TestCase):
    """Test TimeSlot model"""
    
    def setUp(self):
        self.time_slot = TimeSlot.objects.create(
            name="7h-9h",
            start_time=time(7, 0),
            end_time=time(9, 0),
            is_active=True
        )
    
    def test_duration_hours_calculation(self):
        """Test duration_hours() calculates correctly"""
        duration = self.time_slot.duration_hours()
        self.assertEqual(duration, Decimal('2.00'))
    
    def test_duration_hours_with_minutes(self):
        """Test duration_hours() with fractional hours"""
        slot = TimeSlot.objects.create(
            name="7h30-8h45",
            start_time=time(7, 30),
            end_time=time(8, 45)
        )
        duration = slot.duration_hours()
        self.assertEqual(duration, Decimal('1.25'))
    
    def test_clean_invalid_time_range(self):
        """Test clean() raises error when start_time >= end_time"""
        slot = TimeSlot(
            name="invalid",
            start_time=time(9, 0),
            end_time=time(7, 0)
        )
        with self.assertRaises(ValidationError):
            slot.clean()
    
    def test_clean_equal_times(self):
        """Test clean() raises error when times are equal"""
        slot = TimeSlot(
            name="equal",
            start_time=time(7, 0),
            end_time=time(7, 0)
        )
        with self.assertRaises(ValidationError):
            slot.clean()
    
    def test_timeslot_str(self):
        """Test __str__ method"""
        self.assertEqual(str(self.time_slot), "7h-9h")


# ===== PitchTimeSlot Tests =====
class PitchTimeSlotTests(TestCase):
    """Test PitchTimeSlot model"""
    
    def setUp(self):
        self.pitch_type = PitchType.objects.create(name='Football')
        self.facility = Facility.objects.create(
            name='Test Facility',
            address='123 Test St'
        )
        self.pitch = Pitch.objects.create(
            name='Pitch 1',
            facility=self.facility,
            pitch_type=self.pitch_type,
            base_price_per_hour=Decimal('100.00')
        )
        self.time_slot = TimeSlot.objects.create(
            name="7h-9h",
            start_time=time(7, 0),
            end_time=time(9, 0)
        )
        self.pitch_time_slot = PitchTimeSlot.objects.create(
            pitch=self.pitch,
            time_slot=self.time_slot,
            is_available=True
        )
    
    def test_get_price_calculation(self):
        """Test get_price() calculates correctly"""
        price = self.pitch_time_slot.get_price()
        expected = Decimal('100.00') * Decimal('2.00')
        self.assertEqual(price, expected)
    
    def test_get_price_with_decimal_hours(self):
        """Test get_price() with fractional hours"""
        slot = TimeSlot.objects.create(
            name="7h30-9h",
            start_time=time(7, 30),
            end_time=time(9, 0)
        )
        pts = PitchTimeSlot.objects.create(
            pitch=self.pitch,
            time_slot=slot
        )
        price = pts.get_price()
        self.assertEqual(price, Decimal('150.00'))
    
    def test_is_available_on_date_no_bookings(self):
        """Test is_available_on_date() returns True when no conflicts"""
        booking_date = date.today() + timedelta(days=1)
        is_available = self.pitch_time_slot.is_available_on_date(booking_date)
        self.assertTrue(is_available)
    
    def test_is_available_on_date_with_pending_booking(self):
        """Test is_available_on_date() returns False with pending booking"""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        booking_date = date.today() + timedelta(days=1)
        
        Booking.objects.create(
            user=user,
            pitch=self.pitch,
            time_slot=self.pitch_time_slot,
            booking_date=booking_date,
            status=BookingStatus.PENDING
        )
        
        is_available = self.pitch_time_slot.is_available_on_date(booking_date)
        self.assertFalse(is_available)
    
    def test_is_available_on_date_unavailable_slot(self):
        """Test is_available_on_date() returns False when slot unavailable"""
        self.pitch_time_slot.is_available = False
        self.pitch_time_slot.save()
        
        is_available = self.pitch_time_slot.is_available_on_date(date.today() + timedelta(days=1))
        self.assertFalse(is_available)


# ===== Voucher Tests =====
class VoucherTests(TestCase):
    """Test Voucher model"""
    
    def setUp(self):
        self.voucher = Voucher.objects.create(
            code="TEST10",
            discount_percent=10,
            is_active=True
        )
    
    def test_is_valid_active_voucher(self):
        """Test is_valid() returns True for active voucher"""
        self.assertTrue(self.voucher.is_valid())
    
    def test_is_valid_inactive_voucher(self):
        """Test is_valid() returns False for inactive voucher"""
        self.voucher.is_active = False
        self.voucher.save()
        self.assertFalse(self.voucher.is_valid())
    
    def test_is_valid_usage_limit_exceeded(self):
        """Test is_valid() returns False when usage limit exceeded"""
        voucher = Voucher.objects.create(
            code="LIMITED",
            discount_percent=5,
            is_active=True,
            usage_limit=5,
            used_count=5
        )
        self.assertFalse(voucher.is_valid())
    
    def test_is_valid_before_start_date(self):
        """Test is_valid() returns False before start_date"""
        future_date = date.today() + timedelta(days=1)
        voucher = Voucher.objects.create(
            code="FUTURE",
            discount_percent=10,
            is_active=True,
            start_date=future_date
        )
        self.assertFalse(voucher.is_valid())
    
    def test_is_valid_after_end_date(self):
        """Test is_valid() returns False after end_date"""
        past_date = date.today() - timedelta(days=1)
        voucher = Voucher.objects.create(
            code="EXPIRED",
            discount_percent=10,
            is_active=True,
            end_date=past_date
        )
        self.assertFalse(voucher.is_valid())
    
    def test_clean_invalid_date_range(self):
        """Test clean() raises error when start_date > end_date"""
        voucher = Voucher(
            code="INVALID",
            start_date=date.today() + timedelta(days=5),
            end_date=date.today()
        )
        with self.assertRaises(ValidationError):
            voucher.clean()
    
    def test_voucher_str(self):
        """Test __str__ method"""
        self.assertEqual(str(self.voucher), "TEST10")


# ===== Booking Tests =====
class BookingTests(TestCase):
    """Test Booking model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.pitch_type = PitchType.objects.create(name='Football')
        self.facility = Facility.objects.create(
            name='Test Facility',
            address='123 Test St'
        )
        self.pitch = Pitch.objects.create(
            name='Pitch 1',
            facility=self.facility,
            pitch_type=self.pitch_type,
            base_price_per_hour=Decimal('100.00')
        )
        self.time_slot = TimeSlot.objects.create(
            name="7h-9h",
            start_time=time(7, 0),
            end_time=time(9, 0)
        )
        self.pitch_time_slot = PitchTimeSlot.objects.create(
            pitch=self.pitch,
            time_slot=self.time_slot
        )
        self.voucher = Voucher.objects.create(
            code="TEST10",
            discount_percent=10,
            is_active=True
        )
    
    def test_booking_clean_past_date(self):
        """Test clean() rejects past booking dates"""
        booking = Booking(
            user=self.user,
            pitch=self.pitch,
            time_slot=self.pitch_time_slot,
            booking_date=date.today() - timedelta(days=1)
        )
        with self.assertRaises(ValidationError):
            booking.clean()
    
    def test_booking_clean_time_slot_mismatch(self):
        """Test clean() rejects time_slot not belonging to pitch"""
        other_pitch = Pitch.objects.create(
            name='Other Pitch',
            facility=self.facility,
            pitch_type=self.pitch_type,
            base_price_per_hour=Decimal('150.00')
        )
        other_pts = PitchTimeSlot.objects.create(
            pitch=other_pitch,
            time_slot=self.time_slot
        )
        
        booking = Booking(
            user=self.user,
            pitch=self.pitch,
            time_slot=other_pts,
            booking_date=date.today() + timedelta(days=1)
        )
        with self.assertRaises(ValidationError):
            booking.clean()
    
    def test_booking_save_without_voucher(self):
        """Test booking saves correctly without voucher"""
        booking_date = date.today() + timedelta(days=1)
        booking = Booking.objects.create(
            user=self.user,
            pitch=self.pitch,
            time_slot=self.pitch_time_slot,
            booking_date=booking_date
        )
        
        self.assertEqual(booking.duration_hours, Decimal('2.00'))
        self.assertEqual(booking.final_price, Decimal('200.00'))
        self.assertEqual(booking.status, BookingStatus.PENDING)
    
    def test_booking_save_with_valid_voucher(self):
        """Test booking saves with voucher discount applied"""
        booking_date = date.today() + timedelta(days=1)
        booking = Booking.objects.create(
            user=self.user,
            pitch=self.pitch,
            time_slot=self.pitch_time_slot,
            booking_date=booking_date,
            voucher=self.voucher
        )
        
        self.assertEqual(booking.final_price, Decimal('180.00'))
        # Kiểm tra voucher count được tăng
        self.voucher.refresh_from_db()
        self.assertEqual(self.voucher.used_count, 1)
    
    def test_booking_str(self):
        """Test __str__ method"""
        booking_date = date.today() + timedelta(days=1)
        booking = Booking.objects.create(
            user=self.user,
            pitch=self.pitch,
            time_slot=self.pitch_time_slot,
            booking_date=booking_date
        )
        expected = f"{self.pitch.name} - {self.user.username} ({booking_date})"
        self.assertEqual(str(booking), expected)
        