from decimal import Decimal
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from datetime import datetime, date

# ===== User & Roles =====
class Role(models.TextChoices):
    USER = "User", "User"
    ADMIN = "Admin", "Admin"
    GUEST = "Guest", "Guest"

class BookingStatus(models.TextChoices):
    PENDING = "Pending", "Đang chờ xác nhận"
    CONFIRMED = "Confirmed", "Đã xác nhận"
    REJECTED = "Rejected", "Bị từ chối"
    CANCELLED = "Cancelled", "Người dùng hủy"

class User(AbstractUser):
    full_name = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.USER)
    activation_token = models.CharField(max_length=255, unique=True, null=True, blank=True)
    activation_expiry = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.username

# ===== Facility & Pitch =====
class Facility(models.Model):
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self):
        return self.name

class PitchType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    def __str__(self):
        return self.name

class TimeSlot(models.Model):
    """Khung giờ cố định"""
    name = models.CharField(max_length=50)  # "7h-9h"
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['start_time']
        unique_together = ('start_time', 'end_time')

    def __str__(self):
        return self.name

    def clean(self):
        if self.start_time >= self.end_time:
            raise ValidationError("Giờ bắt đầu phải trước giờ kết thúc")

    def duration_hours(self):
        start = datetime.combine(date.today(), self.start_time)
        end = datetime.combine(date.today(), self.end_time)
        duration_float = (end - start).total_seconds() / 3600
        
        return Decimal(duration_float).quantize(Decimal('0.01'))
    
class Pitch(models.Model):
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name="pitches", null=True, blank=True)
    name = models.CharField(max_length=255)
    pitch_type = models.ForeignKey(PitchType, on_delete=models.CASCADE, related_name="pitches")
    base_price_per_hour = models.DecimalField(max_digits=10, decimal_places=2)
    images = models.JSONField(blank=True, null=True)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        facility_name = self.facility.name if self.facility else "No Facility"
        return f"{self.name} - {facility_name}"

    def get_available_time_slots(self, booking_date):
        """Chỉ trả về các slot còn trống"""
        available_slots = []
        for slot in self.time_slots.filter(is_available=True):
            if slot.is_available_on_date(booking_date):
                available_slots.append(slot)
        # Cập nhật luôn is_available theo ngày
        self.is_available = len(available_slots) > 0
        return available_slots

# ===== Liên kết Pitch & TimeSlot =====
class PitchTimeSlot(models.Model):
    """Liên kết sân và khung giờ, dùng base_price_per_hour của sân"""
    pitch = models.ForeignKey(Pitch, on_delete=models.CASCADE, related_name='time_slots')
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE, related_name='pitch_slots')
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('pitch', 'time_slot')
        ordering = ['time_slot__start_time']

    def __str__(self):
        return f"{self.pitch.name} - {self.time_slot.name}"

    def get_price(self):
        """Tính giá dựa trên base_price_per_hour của pitch và duration của time_slot"""
        return self.pitch.base_price_per_hour * self.time_slot.duration_hours()

    def is_available_on_date(self, booking_date):
        """
        Kiểm tra xem PitchTimeSlot này có còn trống vào ngày cụ thể không
        QUAN TRỌNG: time_slot trong Booking là ForeignKey trỏ đến PitchTimeSlot (self),
        không phải TimeSlot
        """
        if not self.is_available:
            return False
        
        # Query booking với time_slot=self (PitchTimeSlot object)
        existing_bookings = Booking.objects.filter(
            pitch=self.pitch,
            booking_date=booking_date,
            time_slot=self,  # ← Truyền PitchTimeSlot object (self), không phải self.time_slot
            status__in=[BookingStatus.PENDING, BookingStatus.CONFIRMED]
        )
        return not existing_bookings.exists()

# ===== Voucher =====
class Voucher(models.Model):
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    discount_percent = models.PositiveIntegerField(default=0)
    min_order_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    used_count = models.PositiveIntegerField(default=0)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError("Ngày bắt đầu phải trước ngày kết thúc.")

    def is_valid(self):
        today = date.today()
        if not self.is_active:
            return False
        if self.usage_limit and self.used_count >= self.usage_limit:
            return False
        if self.start_date and today < self.start_date:
            return False
        if self.end_date and today > self.end_date:
            return False
        return True

    def __str__(self):
        return self.code

# ===== Booking =====
class Booking(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bookings")
    pitch = models.ForeignKey(Pitch, on_delete=models.CASCADE, related_name="bookings")
    time_slot = models.ForeignKey(PitchTimeSlot, on_delete=models.CASCADE, related_name="bookings", null=True, blank=True)
    booking_date = models.DateField()
    duration_hours = models.DecimalField(max_digits=4, decimal_places=2, blank=True)
    final_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True)
    voucher = models.ForeignKey(Voucher, on_delete=models.SET_NULL, null=True, blank=True)
    note = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=10, choices=BookingStatus.choices, default=BookingStatus.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['pitch', 'booking_date', 'status']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['pitch', 'booking_date', 'time_slot']),
        ]

    def clean(self):
        errors = {}
        if self.booking_date and self.booking_date < date.today():
            errors['booking_date'] = "Không thể đặt lịch trong quá khứ."

        if self.pitch and self.time_slot:
            # Kiểm tra xem time_slot có thuộc về pitch không
            if self.time_slot.pitch != self.pitch:
                errors['time_slot'] = "Khung giờ không thuộc về sân này."
            
            # Kiểm tra xem khung giờ còn trống không
            if not self.time_slot.is_available_on_date(self.booking_date):
                errors['time_slot'] = "Khung giờ này đã được đặt."
        
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # Tự động tính duration và final_price từ time_slot
        if self.time_slot:
            self.duration_hours = self.time_slot.time_slot.duration_hours()
            base_price = self.time_slot.get_price()
            
            # Áp dụng voucher nếu có
            if self.voucher and self.voucher.is_valid():
                discount_amount = base_price * Decimal(self.voucher.discount_percent) / Decimal(100)
                self.final_price = base_price - discount_amount
                
                # Tăng used_count của voucher
                if self.pk is None:  # Chỉ tăng khi tạo mới booking
                    self.voucher.used_count += 1
                    self.voucher.save()
            else:
                self.final_price = base_price
        
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.pitch.name} - {self.user.username} ({self.booking_date})"

# ===== Review, Comment, Favorite =====
class Review(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reviews")
    pitch = models.ForeignKey(Pitch, on_delete=models.CASCADE, related_name="reviews")
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'pitch')
        ordering = ['-created_at']
        indexes = [models.Index(fields=['pitch', 'rating'])]

    def __str__(self):
        return f"Review by {self.user.username} for {self.pitch.name} - {self.rating} stars"

class Comment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="comments")
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="comments")
    parent_comment = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name="replies")
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Comment by {self.user.username} on review {self.review.id}"

class Favorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="favorites")
    pitch = models.ForeignKey(Pitch, on_delete=models.CASCADE, related_name="favorited_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "pitch")
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} favorites {self.pitch.name}"
    