from django.contrib import admin
from .models import (
    User, Facility, PitchType, TimeSlot, Pitch, PitchTimeSlot, Voucher,
    Booking, Review, Comment, Favorite
)
from . import constants

class CustomUserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'full_name', 'phone_number', 'role', 'is_staff', 'is_active')
    search_fields = ('username', 'email', 'full_name', 'phone_number')
    readonly_fields = constants.READONLY_TIMESTAMP_FIELDS
    list_per_page = constants.ADMIN_LIST_PER_PAGE
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Thông tin cá nhân', {'fields': ('full_name', 'email', 'phone_number')}),
        ('Quyền hạn & Vai trò', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Kích hoạt tài khoản', {'fields': constants.READONLY_ACTIVATION_FIELDS}),
        ('Ngày giờ', {'fields': ('last_login',) + constants.READONLY_TIMESTAMP_FIELDS}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password', 'role'), 
        }),
    )

class FacilityAdmin(admin.ModelAdmin):
    list_display = ('name', 'address', 'created_at', 'updated_at')
    search_fields = ('name', 'address')
    readonly_fields = constants.READONLY_TIMESTAMP_FIELDS
    list_per_page = constants.ADMIN_LIST_PER_PAGE

class PitchTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)
    list_per_page = constants.ADMIN_LIST_PER_PAGE

class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_time', 'end_time', 'is_active', 'created_at')
    search_fields = ('name',)
    list_filter = ('is_active', 'start_time')
    readonly_fields = ('created_at',)
    ordering = ('start_time',)
    list_per_page = constants.ADMIN_LIST_PER_PAGE

class PitchTimeSlotInline(admin.TabularInline):
    model = PitchTimeSlot
    extra = constants.ADMIN_INLINE_EXTRA
    raw_id_fields = ('time_slot',)
    fields = ('time_slot', 'is_available')

class PitchAdmin(admin.ModelAdmin):
    list_display = ('name', 'pitch_type', 'facility', 'base_price_per_hour', 'is_available', 'created_at')
    search_fields = ('name',)
    list_filter = ('facility', 'pitch_type', 'is_available')
    readonly_fields = constants.READONLY_TIMESTAMP_FIELDS
    ordering = ('name',)
    raw_id_fields = ('pitch_type', 'facility')
    inlines = [PitchTimeSlotInline]
    list_per_page = constants.ADMIN_LIST_PER_PAGE
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('pitch_type', 'facility')

class PitchTimeSlotAdmin(admin.ModelAdmin):
    list_display = ('pitch', 'time_slot', 'is_available', 'get_price_per_slot', 'created_at')
    search_fields = ('pitch__name', 'time_slot__name')
    list_filter = ('is_available', 'time_slot', 'pitch__facility')
    readonly_fields = ('created_at',)
    raw_id_fields = ('pitch', 'time_slot')
    ordering = ('pitch__name', 'time_slot__start_time')
    list_per_page = constants.ADMIN_LIST_PER_PAGE
    
    def get_price_per_slot(self, obj):
        return f"{obj.get_price():,.0f}"
    get_price_per_slot.short_description = "Giá/Slot"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('pitch', 'time_slot', 'pitch__facility')

class VoucherAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_percent', 'min_order_value', 'usage_limit', 'used_count', 'is_active', 'start_date', 'end_date', 'created_at')
    search_fields = ('code', 'description')
    list_filter = ('is_active', 'start_date', 'end_date')
    readonly_fields = constants.VOUCHER_READONLY_FIELDS
    list_editable = ('is_active',)
    list_per_page = constants.ADMIN_LIST_PER_PAGE
    
    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ('code',)
        return self.readonly_fields

class BookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'pitch', 'user', 'time_slot_display', 'booking_date', 'duration_hours', 'final_price_display', 'status')
    search_fields = ('pitch__name', 'user__username', 'user__full_name')
    list_filter = ('status', 'pitch__facility', 'booking_date')
    date_hierarchy = constants.DATE_HIERARCHY_BOOKING
    readonly_fields = constants.BOOKING_READONLY_FIELDS
    raw_id_fields = ('user', 'pitch', 'voucher')
    list_per_page = constants.ADMIN_LIST_PER_PAGE
    
    def time_slot_display(self, obj):
        return obj.time_slot.time_slot.name if obj.time_slot and obj.time_slot.time_slot else "N/A"
    time_slot_display.short_description = "Khung giờ"
    
    def final_price_display(self, obj):
        return f"{obj.final_price:,.0f}" if obj.final_price else "0"
    final_price_display.short_description = "Tổng tiền"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'pitch', 'time_slot__time_slot', 'voucher')
    
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

class ReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'pitch', 'rating', 'created_at', 'updated_at')
    search_fields = ('user__username', 'pitch__name', 'content')
    list_filter = ('rating', 'created_at', 'pitch__facility')
    readonly_fields = constants.READONLY_TIMESTAMP_FIELDS
    raw_id_fields = ('user', 'pitch')
    list_per_page = constants.ADMIN_LIST_PER_PAGE
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'pitch')

class CommentAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'review', 'parent_comment', 'created_at', 'updated_at')
    search_fields = ('user__username', 'review__pitch__name', 'content')
    readonly_fields = constants.READONLY_TIMESTAMP_FIELDS
    raw_id_fields = ('user', 'review', 'parent_comment')
    list_per_page = constants.ADMIN_LIST_PER_PAGE
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'review', 'parent_comment')

class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'pitch', 'created_at')
    search_fields = ('user__username', 'pitch__name')
    list_filter = ('pitch__facility', 'created_at')
    readonly_fields = ('created_at',)
    raw_id_fields = ('user', 'pitch')
    list_per_page = constants.ADMIN_LIST_PER_PAGE
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'pitch')

admin.site.register(User, CustomUserAdmin)
admin.site.register(Facility, FacilityAdmin)
admin.site.register(PitchType, PitchTypeAdmin)
admin.site.register(TimeSlot, TimeSlotAdmin)
admin.site.register(Pitch, PitchAdmin)
admin.site.register(PitchTimeSlot, PitchTimeSlotAdmin)
admin.site.register(Voucher, VoucherAdmin)
admin.site.register(Booking, BookingAdmin)
admin.site.register(Review, ReviewAdmin)
admin.site.register(Comment, CommentAdmin)
admin.site.register(Favorite, FavoriteAdmin)
