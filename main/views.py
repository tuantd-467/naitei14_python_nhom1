# Built-in imports
import re
import logging
from datetime import datetime, date
from smtplib import SMTPException
from django.db import transaction
from django.core.mail import send_mail

# Django imports
from django.http import BadHeaderError, HttpResponseNotAllowed, JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Exists, OuterRef
from django.contrib import messages
from django.utils import timezone
from django.core.files.storage import default_storage
from django.views.decorators.http import require_http_methods, require_POST

# Third-party imports
from django_ratelimit.decorators import ratelimit

from PitchManager import settings

# Local imports
from .utils import (
    send_booking_confirmation_email,
    send_booking_approved_email,
    send_booking_rejection_email,
    send_booking_cancellation_email,
    send_activation_email,
    verify_activation_token
)
from .decorators import user_or_admin_required
from .forms import SignUpForm, BookingForm, DateSelectionForm, ReviewForm, PitchForm
from .models import Booking, Facility, Pitch, PitchTimeSlot, PitchType, Voucher, BookingStatus, Favorite, Role, Review
from . import constants
from django.core.exceptions import ValidationError


logger = logging.getLogger(__name__)


def save_pitch_images(files):
    """
    Save pitch images with sanitized filenames to prevent security issues.
    """
    from django.utils.text import get_valid_filename
    import uuid
    import os
    
    saved_paths = []
    for f in files:
        # Generate unique filename to prevent collisions
        ext = os.path.splitext(f.name)[1]
        unique_name = f"{uuid.uuid4()}{ext}"
        path = default_storage.save(f"pitches/{unique_name}", f)
        saved_paths.append(path)
    return saved_paths

def home(request): 
    q = request.GET.get("q", "") 
    facilities = Facility.objects.all() 
    if q: 
        facilities = facilities.filter(name__icontains=q) 
    context = { 
        'facilities': facilities, 
        'default_facility_image': constants.DEFAULT_FACILITY_IMAGE, 
    } 
    if request.user.is_authenticated: 
        if request.user.role == constants.ROLE_ADMIN: 
            return redirect('admin_booking_list')
        elif request.user.role == constants.ROLE_USER: 
            return render(request, 'main/home.html', context) 
    return render(request, 'main/home.html', context) 


@require_http_methods(["GET", "POST"])
def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    user = form.save(commit=True)
                    send_activation_email(user, request)
                    messages.success(
                        request,
                        'Tài khoản đã được tạo! Vui lòng kiểm tra email để xác thực tài khoản.'
                    )
                    return redirect('login')
            except Exception as e:
                logger.error(f'Email sending failed for user {form.cleaned_data.get("email")}', exc_info=True)
                messages.error(
                    request,
                    'Lỗi gửi email. Vui lòng thử đăng ký lại sau.'
                )
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = SignUpForm()
    return render(request, 'registration/sign-up.html', {'form': form})


@ratelimit(key='ip', rate='5/m', block=True)
def activate_account(request, token):
    try:
        success, message = verify_activation_token(token)
        if success:
            messages.success(request, message)
            return redirect('login')
        else:
            messages.error(request, message)
            return redirect('signup')
    except Exception as e:
        logger.error(f'Error activating account', exc_info=True)
        messages.error(request, 'Có lỗi xảy ra. Vui lòng thử lại sau.')
        return redirect('signup')

def facility_detail(request, facility_id):
    facility = get_object_or_404(Facility, id=facility_id)
    pitches = facility.pitches.filter(is_available=True).select_related('pitch_type')
    
    if request.user.is_authenticated:
        pitch_ids = list(pitches.values_list('id', flat=True))
        
        favorited_pitch_ids = set(Favorite.objects.filter(
            user=request.user,
            pitch_id__in=pitch_ids
        ).values_list('pitch_id', flat=True))
    else:
        favorited_pitch_ids = set()
    
    pitches = list(pitches)
    
    for pitch in pitches:
        pitch.is_favorited = pitch.id in favorited_pitch_ids
    
    context = { 
        'facility': facility, 
        'pitches': pitches, 
        'default_facility_image': constants.DEFAULT_FACILITY_IMAGE, 
        'default_pitch_image': constants.DEFAULT_PITCH_IMAGE, 
        'is_user': request.user.role == constants.ROLE_USER if request.user.is_authenticated else False, 
    } 
    return render(request, 'user/facility_detail.html', context)

def validate_voucher_code(code): 
    if not code: 
        return False, "Mã giảm giá không được để trống" 
    code = code.strip() 
    if len(code) > constants.VOUCHER_CODE_MAX_LENGTH: 
        return False, f"Mã giảm giá không được vượt quá {constants.VOUCHER_CODE_MAX_LENGTH} ký tự" 
    if not re.match(constants.VOUCHER_CODE_PATTERN, code): 
        return False, "Mã giảm giá chỉ được chứa chữ cái, số, dấu gạch ngang và gạch dưới" 
    return True, "" 

def pitch_list(request): 
    pitches = Pitch.objects.select_related('pitch_type', 'facility').all() 
    search_query = request.GET.get('q', '') 
    pitch_type_filter = request.GET.get('pitch_type', '') 
    price_range_filter = request.GET.get('price_range', '') 
    booking_date_filter = request.GET.get('booking_date', '') 
    sort_by = request.GET.get('sort', 'name') 
    
    if search_query: 
        pitches = pitches.filter( 
            Q(name__icontains=search_query) | 
            Q(facility__name__icontains=search_query) | 
            Q(facility__address__icontains=search_query) 
        ) 
    
    if pitch_type_filter: 
        pitches = pitches.filter(pitch_type_id=pitch_type_filter) 
    
    if price_range_filter and price_range_filter in constants.PRICE_RANGES: 
        min_price, max_price = constants.PRICE_RANGES[price_range_filter] 
        if max_price == float('inf'): 
            pitches = pitches.filter(base_price_per_hour__gte=min_price) 
        else: 
            pitches = pitches.filter( 
                base_price_per_hour__gte=min_price, 
                base_price_per_hour__lte=max_price 
            ) 
    
    if booking_date_filter: 
        try: 
            booking_date = datetime.strptime(booking_date_filter, '%Y-%m-%d').date() 
            available_time_slots = PitchTimeSlot.objects.filter( 
                pitch=OuterRef('pk'), 
                is_available=True 
            ).exclude( 
                bookings__booking_date=booking_date, 
                bookings__status__in=[BookingStatus.PENDING, BookingStatus.CONFIRMED] 
            ) 
            pitches = pitches.annotate( 
                has_available_slots=Exists(available_time_slots) 
            ).filter( 
                has_available_slots=True, 
                is_available=True 
            ) 
        except ValueError: 
            pass 
    
    if sort_by == 'name': 
        pitches = pitches.order_by('name') 
    elif sort_by == '-name': 
        pitches = pitches.order_by('-name') 
    elif sort_by == 'price': 
        pitches = pitches.order_by('base_price_per_hour') 
    elif sort_by == '-price': 
        pitches = pitches.order_by('-base_price_per_hour') 
    else: 
        pitches = pitches.order_by('name') 
    
    has_filters = any([search_query, pitch_type_filter, price_range_filter, booking_date_filter]) 
    pitch_types = PitchType.objects.all() 
    paginator = Paginator(pitches, constants.ITEMS_PER_PAGE) 
    page_number = request.GET.get('page') 
    
    try: 
        pitches_page = paginator.page(page_number) 
    except PageNotAnInteger: 
        pitches_page = paginator.page(1) 
    except EmptyPage: 
        pitches_page = paginator.page(paginator.num_pages) 
    
    if request.user.is_authenticated:
        pitch_ids = [p.id for p in pitches_page]
        favorited_pitch_ids = set(Favorite.objects.filter(
            user=request.user,
            pitch_id__in=pitch_ids
        ).values_list('pitch_id', flat=True))
    else:
        favorited_pitch_ids = set()
    
    for pitch in pitches_page:
        pitch.is_favorited = pitch.id in favorited_pitch_ids
    
    request_get_dict = dict(request.GET.items())
    
    context = { 
        'pitches': pitches_page, 
        'pitch_types': pitch_types, 
        'has_filters': has_filters, 
        'request_get': request_get_dict, 
        'selected_booking_date': booking_date_filter, 
        'default_pitch_image': constants.DEFAULT_PITCH_IMAGE, 
    } 
    return render(request, 'user/pitch_list.html', context)

@login_required(login_url='login') 
def book_pitch(request, pitch_id): 
    if request.user.role != constants.ROLE_USER: 
        return HttpResponseForbidden("Bạn không có quyền đặt sân!") 
    
    pitch = get_object_or_404(Pitch, id=pitch_id) 
    
    pitch.is_favorited = Favorite.objects.filter(
        user=request.user,
        pitch=pitch
    ).exists()
    
    selected_date = request.GET.get('booking_date', '') 
    voucher_code = request.GET.get('voucher_code', '') 
    date_form = DateSelectionForm(initial={'booking_date': selected_date}) 
    available_time_slots = [] 
    time_slot_choices = [] 
    
    if selected_date: 
        try: 
            booking_date = datetime.strptime(selected_date, '%Y-%m-%d').date() 
            all_pitch_time_slots = PitchTimeSlot.objects.filter( 
                pitch=pitch, 
                is_available=True
            ).select_related('time_slot')
            
            if all_pitch_time_slots.count() == 0:
                pass
            
            for pitch_time_slot in all_pitch_time_slots: 
                is_available = pitch_time_slot.is_available_on_date(booking_date) 
                
                if is_available: 
                    price = pitch_time_slot.get_price() 
                    slot_data = { 
                        'id': pitch_time_slot.id, 
                        'time_slot': pitch_time_slot.time_slot, 
                        'duration_hours': pitch_time_slot.time_slot.duration_hours(), 
                        'price': price 
                    } 
                    available_time_slots.append(slot_data) 
                    time_slot_choices.append((pitch_time_slot.id, slot_data)) 
            
        except ValueError:
            selected_date = ''
    
    voucher_message = '' 
    voucher_message_type = 'text-muted' 
    if voucher_code: 
        is_valid_format, error_message = validate_voucher_code(voucher_code) 
        
        if not is_valid_format: 
            voucher_message = error_message 
            voucher_message_type = 'text-danger' 
        else: 
            voucher_code_clean = voucher_code.strip().upper() 
            
            try: 
                voucher = Voucher.objects.get(code=voucher_code_clean) 
                if voucher.is_valid(): 
                    voucher_message = f'Mã giảm giá {voucher.discount_percent}% có hiệu lực' 
                    voucher_message_type = 'text-success' 
                else: 
                    voucher_message = 'Mã giảm giá không hợp lệ hoặc đã hết hạn' 
                    voucher_message_type = 'text-danger' 
            except Voucher.DoesNotExist: 
                voucher_message = 'Mã giảm giá không tồn tại' 
                voucher_message_type = 'text-danger' 
    
    booking_form = BookingForm( 
        initial={ 
            'booking_date': selected_date, 
            'voucher_code': voucher_code 
        }, 
        time_slot_choices=time_slot_choices 
    ) 
    
    if request.method == 'POST': 
        booking_form = BookingForm(request.POST, time_slot_choices=time_slot_choices) 
        if booking_form.is_valid(): 
            booking_date = booking_form.cleaned_data['booking_date'] 
            time_slot_id = booking_form.cleaned_data['time_slot'] 
            voucher_code = booking_form.cleaned_data['voucher_code'] 
            note = booking_form.cleaned_data['note'] 
            
            try: 
                pitch_time_slot = PitchTimeSlot.objects.select_related('time_slot').get( 
                    id=time_slot_id, 
                    pitch=pitch 
                ) 
                
                booking = Booking( 
                    user=request.user, 
                    pitch=pitch, 
                    time_slot=pitch_time_slot, 
                    booking_date=booking_date, 
                    note=note 
                ) 
                
                if voucher_code: 
                    is_valid_format, error_message = validate_voucher_code(voucher_code) 
                    
                    if is_valid_format: 
                        voucher_code_clean = voucher_code.strip().upper() 
                        try: 
                            voucher = Voucher.objects.get(code=voucher_code_clean) 
                            if voucher.is_valid(): 
                                booking.voucher = voucher 
                            else: 
                                messages.warning(request, 'Mã giảm giá không hợp lệ, đặt sân không áp dụng giảm giá.') 
                        except Voucher.DoesNotExist: 
                            messages.warning(request, 'Mã giảm giá không tồn tại, đặt sân không áp dụng giảm giá.') 
                    else: 
                        messages.warning(request, f'{error_message}, đặt sân không áp dụng giảm giá.') 
                
                booking.save()
                logger.info(f"Booking created: #{booking.id} by user {request.user.username}")
                messages.success(request, f'Đặt sân thành công! Mã đặt sân: #{booking.id}')
                return redirect('pitch_list')
                
            except (PitchTimeSlot.DoesNotExist, ValueError) as e:
                logger.error(f"Error creating booking", exc_info=True)
                messages.error(request, 'Có lỗi xảy ra khi đặt sân. Vui lòng thử lại.')
    
    context = { 
        'pitch': pitch, 
        'selected_date': selected_date, 
        'available_time_slots': available_time_slots, 
        'voucher_code': voucher_code, 
        'voucher_message': voucher_message, 
        'voucher_message_type': voucher_message_type, 
        'today': date.today().isoformat(), 
        'date_form': date_form, 
        'booking_form': booking_form, 
        'default_pitch_image': constants.DEFAULT_PITCH_IMAGE, 
    } 
    
    return render(request, 'user/book_pitch.html', context)


@login_required(login_url='login')
def admin_pitch_list(request):
    if request.user.role != constants.ROLE_ADMIN:
        return HttpResponseForbidden("Bạn không có quyền truy cập trang quản lý sân.")

    pitches = Pitch.objects.select_related("pitch_type", "facility").all()
    return render(request, "host/pitch_admin_list.html", {"pitches": pitches})


@require_http_methods(["GET", "POST"])
def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    user = form.save(commit=True)
                    send_activation_email(user, request)
                    messages.success(
                        request,
                        'Tài khoản đã được tạo! Vui lòng kiểm tra email để xác thực tài khoản.')
                    return redirect('login')
            except Exception as e:
                logger.error(
                    f'Email sending failed for user {form.cleaned_data.get("email")}',
                    exc_info=True)
                messages.error(
                    request,
                    'Lỗi gửi email. Vui lòng thử đăng ký lại sau.'
                )
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = SignUpForm()
    return render(request, 'registration/sign-up.html', {'form': form})


@login_required(login_url='login')
def admin_pitch_create(request):
    if request.user.role != constants.ROLE_ADMIN:
        return HttpResponseForbidden("Bạn không có quyền truy cập trang quản lý sân.")

    form = PitchForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        pitch = form.save(commit=False)
        images = form.clean_multiple_images()
        if images:
            pitch.images = save_pitch_images(images)
        pitch.save()
        messages.success(request, "Tạo sân thành công.")
        return redirect("admin_pitch_list")

    return render(request, "host/pitch_form.html", {"form": form, "is_edit": False})


@login_required(login_url='login')
def admin_pitch_update(request, pitch_id):
    if request.user.role != constants.ROLE_ADMIN:
        return HttpResponseForbidden("Bạn không có quyền truy cập trang quản lý sân.")

    pitch = get_object_or_404(Pitch, id=pitch_id)
    form = PitchForm(request.POST or None, request.FILES or None, instance=pitch)

    if request.method == "POST" and form.is_valid():
        pitch = form.save(commit=False)
        images = form.clean_multiple_images()
        if images:
            pitch.images = save_pitch_images(images)
        pitch.save()
        messages.success(request, "Cập nhật sân thành công.")
        return redirect("admin_pitch_list")

    return render(
        request,
        "host/pitch_form.html",
        {"form": form, "is_edit": True, "pitch": pitch},
    )


@login_required(login_url='login')
def admin_pitch_delete(request, pitch_id):
    if request.user.role != constants.ROLE_ADMIN:
        return HttpResponseForbidden("Bạn không có quyền truy cập trang quản lý sân.")

    pitch = get_object_or_404(Pitch, id=pitch_id)
    has_blocking = pitch.bookings.filter(
        status__in=[BookingStatus.PENDING, BookingStatus.CONFIRMED]
    ).exists()

    if has_blocking:
        messages.error(
            request,
            "Không thể xóa sân vì đang có đơn đặt sân ở trạng thái Đang chờ/Đã xác nhận.",
        )
        return redirect("admin_pitch_list")

    pitch.delete()
    messages.success(request, "Đã xóa sân thành công.")
    return redirect("admin_pitch_list")


def home(request):
    q = request.GET.get("q", "")
    facilities = Facility.objects.all()
    if q:
        facilities = facilities.filter(name__icontains=q)
    context = {
        'facilities': facilities,
        'default_facility_image': constants.DEFAULT_FACILITY_IMAGE,
    }
    if request.user.is_authenticated:
        if request.user.role == constants.ROLE_ADMIN:
            return render(request, 'host/pitch_manage.html', context)
        elif request.user.role == constants.ROLE_USER:
            return render(request, 'main/home.html', context)
    return render(request, 'main/home.html', context)


@login_required(login_url='login')
def admin_booking_list(request):
    """Trang admin: xem + filter đơn đặt sân, kèm nút approve/reject."""
    if request.user.role != constants.ROLE_ADMIN:
        return HttpResponseForbidden(
            "Bạn không có quyền truy cập trang quản lý đơn đặt sân.")

    status_filter = request.GET.get("status", "")
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")

    bookings = (
        Booking.objects
        .select_related("user", "pitch", "pitch__facility")
        .all()
        .order_by("-created_at")
    )

    if status_filter:
        bookings = bookings.filter(status=status_filter)

    if date_from:
        try:
            date_from_parsed = datetime.strptime(date_from, "%Y-%m-%d").date()
            bookings = bookings.filter(booking_date__gte=date_from_parsed)
        except ValueError:
            messages.warning(request, "Định dạng ngày 'từ ngày' không hợp lệ.")
            date_from = ""

    if date_to:
        try:
            date_to_parsed = datetime.strptime(date_to, "%Y-%m-%d").date()
            bookings = bookings.filter(booking_date__lte=date_to_parsed)
        except ValueError:
            messages.warning(
                request, "Định dạng ngày 'đến ngày' không hợp lệ.")
            date_to = ""

    paginator = Paginator(bookings, constants.ADMIN_LIST_PER_PAGE)
    page_number = request.GET.get("page")

    try:
        bookings_page = paginator.page(page_number)
    except PageNotAnInteger:
        bookings_page = paginator.page(1)
    except EmptyPage:
        bookings_page = paginator.page(paginator.num_pages)

    context = {
        "bookings": bookings_page,
        "status_filter": status_filter,
        "date_from": date_from,
        "date_to": date_to,
        "status_choices": BookingStatus.choices,
        "booking_status": BookingStatus,
    }
    return render(request, "host/pitch_manage.html", context)


@login_required(login_url='login')
def admin_update_booking_status(request, booking_id):
    """Admin approve/reject đơn và gửi email cho user."""
    if request.user.role != constants.ROLE_ADMIN:
        return HttpResponseForbidden(
            "Bạn không có quyền cập nhật đơn đặt sân.")

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    booking = get_object_or_404(Booking, pk=booking_id)

    action = request.POST.get("action")
    if action == "approve":
        new_status = BookingStatus.CONFIRMED
        subject = "Đơn đặt sân của bạn đã được xác nhận"
        message = (
            f"Xin chào {booking.user.full_name or booking.user.username},\n\n"
            f"Đơn đặt sân #{booking.id} tại sân {booking.pitch.name} ngày {booking.booking_date} "
            f"đã được xác nhận.\n\n"
            "Cảm ơn bạn đã sử dụng dịch vụ!")
        success_msg = "Đã xác nhận đơn đặt sân."
    elif action == "reject":
        new_status = BookingStatus.REJECTED
        subject = "Đơn đặt sân của bạn đã bị từ chối"
        message = (
            f"Xin chào {booking.user.full_name or booking.user.username},\n\n"
            f"Rất tiếc, đơn đặt sân #{booking.id} tại sân {booking.pitch.name} ngày {booking.booking_date} "
            f"đã bị từ chối.\n\n"
            "Vui lòng liên hệ quản trị viên để biết thêm chi tiết.")
        success_msg = "Đã từ chối đơn đặt sân."
    else:
        messages.error(request, "Hành động không hợp lệ.")
        return redirect("admin_booking_list")

    if booking.status != BookingStatus.PENDING:
        messages.error(
            request,
            "Chỉ có thể cập nhật đơn đặt sân đang chờ xác nhận.")
        return redirect("admin_booking_list")

    old_status = booking.status
    booking.status = new_status
    booking.save(update_fields=["status"])

    if (
        booking.voucher
        and old_status == BookingStatus.PENDING
        and new_status == BookingStatus.CONFIRMED
    ):
        booking.voucher.used_count += 1
        booking.voucher.save(update_fields=["used_count"])

    if booking.user.email:
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                recipient_list=[booking.user.email],
                fail_silently=True,
            )
        except (BadHeaderError, SMTPException):
            messages.warning(
                request, "Cập nhật trạng thái thành công nhưng gửi email thất bại.")
        else:
            messages.success(
                request, f"{success_msg} Email thông báo đã được gửi.")
    else:
        messages.success(
            request,
            f"{success_msg} (User không có email để gửi thông báo).")

    return redirect("admin_booking_list")


def facility_detail(request, facility_id):
    facility = get_object_or_404(Facility, id=facility_id)
    pitches = facility.pitches.filter(is_available=True)

    context = {
        'facility': facility,
        'pitches': pitches,
        'default_facility_image': constants.DEFAULT_FACILITY_IMAGE,
        'default_pitch_image': constants.DEFAULT_PITCH_IMAGE,
        'is_user': request.user.role == constants.ROLE_USER if request.user.is_authenticated else False,
    }

    return render(request, 'user/facility_detail.html', context)


def validate_voucher_code(code):
    """
    Validate voucher code format
    Returns: (is_valid, error_message)
    """
    if not code:
        return False, "Mã giảm giá không được để trống"

    # Remove whitespace
    code = code.strip()

    # Check length
    if len(code) > constants.VOUCHER_CODE_MAX_LENGTH:
        return False, f"Mã giảm giá không được vượt quá {constants.VOUCHER_CODE_MAX_LENGTH} ký tự"

    # Check for valid characters
    if not re.match(constants.VOUCHER_CODE_PATTERN, code):
        return False, "Mã giảm giá chỉ được chứa chữ cái, số, dấu gạch ngang và gạch dưới"

    return True, ""


def pitch_list(request):
    pitches = Pitch.objects.select_related('pitch_type', 'facility').all()

    search_query = request.GET.get('q', '')
    pitch_type_filter = request.GET.get('pitch_type', '')
    price_range_filter = request.GET.get('price_range', '')
    booking_date_filter = request.GET.get('booking_date', '')
    sort_by = request.GET.get('sort', 'name')

    # Filter by search query
    if search_query:
        pitches = pitches.filter(
            Q(name__icontains=search_query) |
            Q(facility__name__icontains=search_query) |
            Q(facility__address__icontains=search_query)
        )

    # Filter by pitch type
    if pitch_type_filter:
        pitches = pitches.filter(pitch_type_id=pitch_type_filter)

    # Filter by price range using constants
    if price_range_filter and price_range_filter in constants.PRICE_RANGES:
        min_price, max_price = constants.PRICE_RANGES[price_range_filter]
        if max_price == float('inf'):
            pitches = pitches.filter(base_price_per_hour__gte=min_price)
        else:
            pitches = pitches.filter(
                base_price_per_hour__gte=min_price,
                base_price_per_hour__lte=max_price
            )

    # Filter by booking date availability
    if booking_date_filter:
        try:
            booking_date = datetime.strptime(
                booking_date_filter, '%Y-%m-%d').date()

            available_time_slots = PitchTimeSlot.objects.filter(
                pitch=OuterRef('pk'), is_available=True).exclude(
                bookings__booking_date=booking_date, bookings__status__in=[
                    BookingStatus.PENDING, BookingStatus.CONFIRMED])

            pitches = pitches.annotate(
                has_available_slots=Exists(available_time_slots)
            ).filter(
                has_available_slots=True,
                is_available=True
            )

        except ValueError:
            pass

    # Sorting
    if sort_by == 'name':
        pitches = pitches.order_by('name')
    elif sort_by == '-name':
        pitches = pitches.order_by('-name')
    elif sort_by == 'price':
        pitches = pitches.order_by('base_price_per_hour')
    elif sort_by == '-price':
        pitches = pitches.order_by('-base_price_per_hour')
    else:
        pitches = pitches.order_by('name')

    has_filters = any([search_query, pitch_type_filter,
                      price_range_filter, booking_date_filter])

    pitch_types = PitchType.objects.all()

    # Pagination using constant
    paginator = Paginator(pitches, constants.ITEMS_PER_PAGE)
    page_number = request.GET.get('page')

    try:
        pitches_page = paginator.page(page_number)
    except PageNotAnInteger:
        pitches_page = paginator.page(1)
    except EmptyPage:
        pitches_page = paginator.page(paginator.num_pages)

    # Convert request.GET to dict for template
    request_get_dict = {}
    for key, value in request.GET.items():
        request_get_dict[key] = value

    context = {
        'pitches': pitches_page,
        'pitch_types': pitch_types,
        'has_filters': has_filters,
        'request_get': request_get_dict,
        'selected_booking_date': booking_date_filter,
        'default_pitch_image': constants.DEFAULT_PITCH_IMAGE,
    }

    return render(request, 'user/pitch_list.html', context)


def _apply_voucher_to_booking(booking, voucher_code, request):
    """Helper: Apply voucher to booking if valid"""
    if not voucher_code:
        return

    is_valid_format, error_message = validate_voucher_code(voucher_code)

    if not is_valid_format:
        messages.warning(
            request,
            f'{error_message}, đặt sân không áp dụng giảm giá.')
        return

    voucher_code_clean = voucher_code.strip().upper()
    try:
        voucher = Voucher.objects.get(code=voucher_code_clean)
        if voucher.is_valid():
            booking.voucher = voucher
            messages.success(
                request, f'Đã áp dụng mã giảm giá {voucher.discount_percent}%!')
        else:
            messages.warning(request, constants.ERR_VOUCHER_INVALID)
    except Voucher.DoesNotExist:
        messages.warning(request, constants.ERR_VOUCHER_NOT_FOUND)


# ============= USER BOOKING VIEWS =============

@user_or_admin_required
def user_booking_create(request, pitch_id):
    """
    Tạo booking mới

    Flow:
    1. User chọn ngày → hiển thị available time slots
    2. User chọn time slot + voucher (optional) → tạo booking
    3. Gửi email xác nhận → redirect to booking detail
    """
    pitch = get_object_or_404(Pitch, id=pitch_id, is_available=True)

    # Get booking date from GET or POST
    if request.method == 'POST':
        booking_date_str = request.POST.get('booking_date')
    else:
        booking_date_str = request.GET.get('date')

    booking_date = None

    if booking_date_str:
        try:
            booking_date = datetime.strptime(
                booking_date_str, '%Y-%m-%d').date()
        except ValueError:
            booking_date = None

    # Load available time slots for selected date to populate form choices
    available_time_slots = []
    time_slot_choices = []

    # Get reviews
    reviews = Review.objects.filter(pitch=pitch).select_related(
        'user').order_by('-created_at')

    # Check if user can review
    can_review = False
    has_reviewed = False
    if request.user.is_authenticated:
        has_booked = Booking.objects.filter(
            user=request.user,
            pitch=pitch,
            status=BookingStatus.CONFIRMED
        ).exists()

        has_reviewed = Review.objects.filter(
            user=request.user, pitch=pitch).exists()
        can_review = has_booked and not has_reviewed

    if booking_date:
        all_time_slots = PitchTimeSlot.objects.filter(
            pitch=pitch,
            is_available=True
        ).select_related('time_slot').order_by('time_slot__start_time')

        for pts in all_time_slots:
            is_available = pts.is_available_on_date(booking_date)

            # Prepare data for template
            slot_data = {
                'id': pts.id,
                'name': pts.time_slot.name,
                'start_time': pts.time_slot.start_time,
                'end_time': pts.time_slot.end_time,
                'duration': pts.time_slot.duration_hours(),
                'price': pts.get_price(),
                'is_available': is_available
            }
            available_time_slots.append(slot_data)

            # Prepare choices for form validation (only available slots if we want strict validation,
            # but usually we allow all and validate availability in clean)
            # Here we add all slots to choices so form validation passes "invalid choice" check,
            # availability is checked in Booking.clean() or manually.
            time_slot_choices.append((str(pts.id), pts.time_slot.name))

    if request.method == 'POST':
        form = BookingForm(
            request.POST,
            time_slot_choices=time_slot_choices
        )

        if form.is_valid():
            # BookingForm is not a ModelForm, so we create Booking manually
            time_slot_id = form.cleaned_data.get('time_slot')
            note = form.cleaned_data.get('note')
            voucher_code = form.cleaned_data.get('voucher_code')

            try:
                pitch_time_slot = PitchTimeSlot.objects.get(
                    id=time_slot_id, pitch=pitch)

                booking = Booking(
                    user=request.user,
                    pitch=pitch,
                    time_slot=pitch_time_slot,
                    booking_date=booking_date,
                    note=note
                )

                # Apply voucher if provided
                _apply_voucher_to_booking(booking, voucher_code, request)

                # Save booking (auto-calculate duration & price in model)
                booking.save()

                # Send confirmation email
                send_booking_confirmation_email(booking)

                messages.success(request, constants.MSG_BOOKING_CREATED)
                return redirect('user_booking_detail', booking_id=booking.id)

            except PitchTimeSlot.DoesNotExist:
                messages.error(request, "Khung giờ không hợp lệ.")
            except ValidationError as e:
                messages.error(request, str(e))
            except Exception as e:
                logger.error(f"Error creating booking: {e}", exc_info=True)
                messages.error(request, "Có lỗi xảy ra khi đặt sân.")
    else:
        form = BookingForm(
            initial={'booking_date': booking_date},
            time_slot_choices=time_slot_choices
        )

    context = {
        'form': form,
        'pitch': pitch,
        'booking_date': booking_date,
        'available_time_slots': available_time_slots,
        'today': date.today().isoformat(),
        'default_pitch_image': constants.DEFAULT_PITCH_IMAGE,
        'reviews': reviews,
        'can_review': can_review,
        'has_reviewed': has_reviewed,
        'review_form': ReviewForm() if can_review else None,
    }
    return render(request, 'user/booking_create.html', context)


@user_or_admin_required
def user_booking_list(request):
    """Danh sách booking của user (hoặc tất cả nếu là admin)"""
    if request.user.role == Role.ADMIN:
        bookings = Booking.objects.all()
    else:
        bookings = Booking.objects.filter(user=request.user)

    bookings = bookings.select_related(
        'pitch', 'time_slot__time_slot', 'voucher'
    ).order_by('-booking_date', '-created_at')

    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter:
        bookings = bookings.filter(status=status_filter)

    # Pagination
    paginator = Paginator(bookings, constants.BOOKINGS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'booking_statuses': BookingStatus.choices,
        'is_admin': request.user.role == Role.ADMIN,
    }
    return render(request, 'user/booking_list.html', context)


@user_or_admin_required
def user_booking_detail(request, booking_id):
    """Chi tiết booking"""
    if request.user.role == Role.ADMIN:
        booking = get_object_or_404(Booking, id=booking_id)
    else:
        booking = get_object_or_404(Booking, id=booking_id, user=request.user)

    context = {
        'booking': booking,
        'is_admin': request.user.role == Role.ADMIN,
        'can_cancel': booking.status == BookingStatus.PENDING,
        'can_approve': (
            request.user.role == Role.ADMIN
            and booking.status == BookingStatus.PENDING),
    }
    return render(request, 'user/booking_detail.html', context)


@user_or_admin_required
def user_booking_cancel(request, booking_id):
    """Hủy booking (chỉ với status PENDING)"""
    if request.user.role == Role.ADMIN:
        booking = get_object_or_404(Booking, id=booking_id)
    else:
        booking = get_object_or_404(Booking, id=booking_id, user=request.user)

    if booking.status != BookingStatus.PENDING:
        messages.error(request, constants.ERR_BOOKING_ONLY_CANCEL_PENDING)
        return redirect('user_booking_detail', booking_id=booking_id)

    if request.method == 'POST':

        booking.status = BookingStatus.CANCELLED
        booking.save(update_fields=['status'])

        # Send cancellation email
        send_booking_cancellation_email(booking)

        messages.success(request, constants.MSG_BOOKING_CANCELLED)
        return redirect('user_booking_list')

    context = {
        'booking': booking,
        'is_admin': request.user.role == Role.ADMIN,
    }
    return render(request, 'user/booking_cancel.html', context)


# ============= ADMIN BOOKING VIEWS =============

@login_required
def admin_booking_approve(request, booking_id):
    """Admin duyệt booking (PENDING → CONFIRMED)"""
    if request.user.role != Role.ADMIN:
        messages.error(request, constants.ERR_NO_PERMISSION)
        return redirect('home')

    booking = get_object_or_404(Booking, id=booking_id)

    if booking.status != BookingStatus.PENDING:
        messages.error(request, constants.ERR_BOOKING_ONLY_APPROVE_PENDING)
        return redirect('user_booking_detail', booking_id=booking_id)

    booking.status = BookingStatus.CONFIRMED
    booking.save()

    # Send approval email to user
    send_booking_approved_email(booking)

    messages.success(
        request,
        constants.MSG_BOOKING_APPROVED.format(
            booking_id=booking.id))
    return redirect('user_booking_list')


@login_required
def admin_booking_reject(request, booking_id):
    """Admin từ chối booking (PENDING → REJECTED)"""
    if request.user.role != Role.ADMIN:
        messages.error(request, constants.ERR_NO_PERMISSION)
        return redirect('home')

    booking = get_object_or_404(Booking, id=booking_id)

    if booking.status != BookingStatus.PENDING:
        messages.error(request, constants.ERR_BOOKING_ONLY_APPROVE_PENDING)
        return redirect('user_booking_detail', booking_id=booking_id)

    # Get rejection reason from POST if available
    reason = request.POST.get('reason', '') if request.method == 'POST' else ''

    booking.status = BookingStatus.REJECTED
    booking.save()

    # Send rejection email to user
    send_booking_rejection_email(booking, reason=reason)

    messages.warning(
        request,
        constants.MSG_BOOKING_REJECTED.format(
            booking_id=booking.id))
    return redirect('user_booking_list')


def get_available_time_slots_ajax(request, pitch_id):
    """AJAX: Lấy available time slots cho ngày cụ thể"""
    pitch = get_object_or_404(Pitch, id=pitch_id)
    date_str = request.GET.get('date')

    if not date_str:
        return JsonResponse({'error': 'Missing date parameter'}, status=400)

    try:
        booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Invalid date format'}, status=400)

    all_time_slots = PitchTimeSlot.objects.filter(
        pitch=pitch,
        is_available=True
    ).select_related('time_slot').order_by('time_slot__start_time')

    slots_data = []
    for pts in all_time_slots:
        slots_data.append({
            'id': pts.id,
            'name': pts.time_slot.name,
            'start_time': pts.time_slot.start_time.strftime('%H:%M'),
            'end_time': pts.time_slot.end_time.strftime('%H:%M'),
            'duration': float(pts.time_slot.duration_hours()),
            'price': float(pts.get_price()),
            'is_available': pts.is_available_on_date(booking_date)
        })

    return JsonResponse({'date': date_str, 'slots': slots_data})


def check_voucher_ajax(request):
    """AJAX: Kiểm tra mã giảm giá"""
    code = request.GET.get('code', '')

    if not code:
        return JsonResponse(
            {'valid': False, 'message': 'Vui lòng nhập mã giảm giá'})

    is_valid_format, error_message = validate_voucher_code(code)

    if not is_valid_format:
        return JsonResponse({'valid': False, 'message': error_message})

    code_clean = code.strip().upper()

    try:
        voucher = Voucher.objects.get(code=code_clean)
        if voucher.is_valid():
            return JsonResponse({
                'valid': True,
                'message': f'Mã giảm {voucher.discount_percent}% có hiệu lực!',
                'discount_percent': voucher.discount_percent
            })
        else:
            return JsonResponse(
                {'valid': False, 'message': 'Mã giảm giá đã hết hạn'})
    except Voucher.DoesNotExist:
        return JsonResponse(
            {'valid': False, 'message': 'Mã giảm giá không tồn tại'})


@user_or_admin_required
def user_toggle_favorite(request, pitch_id):
    """Toggle yêu thích sân"""
    pitch = get_object_or_404(Pitch, id=pitch_id)

    favorite, created = Favorite.objects.get_or_create(
        user=request.user,
        pitch=pitch
    )

    if not created:
        favorite.delete()
        messages.info(request, f'Đã bỏ yêu thích {pitch.name}.')
        is_favorited = False
    else:
        messages.success(request, f'Đã thêm {pitch.name} vào yêu thích.')
        is_favorited = True

    # Return JSON for AJAX or redirect for normal request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'is_favorited': is_favorited})

    return redirect('facility_detail', facility_id=pitch.facility.id)


@user_or_admin_required
def user_favorites(request):
    """Danh sách sân yêu thích"""
    favorites = Favorite.objects.filter(
        user=request.user
    ).select_related('pitch', 'pitch__facility')

    context = {
        'favorites': favorites,
        'default_pitch_image': constants.DEFAULT_PITCH_IMAGE,
    }
    return render(request, 'user/favorites.html', context)


@login_required(login_url='login')
def book_pitch(request, pitch_id):
    if request.user.role != constants.ROLE_USER:
        return HttpResponseForbidden("Bạn không có quyền đặt sân!")

    pitch = get_object_or_404(Pitch, id=pitch_id)

    pitch.is_favorited = Favorite.objects.filter(
        user=request.user,
        pitch=pitch
    ).exists()

    selected_date = request.GET.get('booking_date', '')
    voucher_code = request.GET.get('voucher_code', '')
    date_form = DateSelectionForm(initial={'booking_date': selected_date})
    available_time_slots = []
    time_slot_choices = []

    if selected_date:
        try:
            booking_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
            all_pitch_time_slots = PitchTimeSlot.objects.filter(
                pitch=pitch,
                is_available=True
            ).select_related('time_slot')

            if all_pitch_time_slots.count() == 0:
                logger.warning(
                    f"No PitchTimeSlots available for pitch {pitch.id}")

            for pitch_time_slot in all_pitch_time_slots:
                is_available = pitch_time_slot.is_available_on_date(
                    booking_date)

                if is_available:
                    price = pitch_time_slot.get_price()
                    slot_data = {
                        'id': pitch_time_slot.id,
                        'time_slot': pitch_time_slot.time_slot,
                        'duration_hours': pitch_time_slot.time_slot.duration_hours(),
                        'price': price}
                    available_time_slots.append(slot_data)
                    time_slot_choices.append((pitch_time_slot.id, slot_data))

        except ValueError as e:
            logger.error(
                f"Invalid date format for booking: {selected_date}",
                exc_info=True)
            selected_date = ''

    voucher_message = ''
    voucher_message_type = 'text-muted'
    if voucher_code:
        is_valid_format, error_message = validate_voucher_code(voucher_code)

        if not is_valid_format:
            voucher_message = error_message
            voucher_message_type = 'text-danger'
        else:
            voucher_code_clean = voucher_code.strip().upper()

            try:
                voucher = Voucher.objects.get(code=voucher_code_clean)
                if voucher.is_valid():
                    voucher_message = f'Mã giảm giá {voucher.discount_percent}% có hiệu lực'
                    voucher_message_type = 'text-success'
                else:
                    voucher_message = 'Mã giảm giá không hợp lệ hoặc đã hết hạn'
                    voucher_message_type = 'text-danger'
            except Voucher.DoesNotExist:
                voucher_message = 'Mã giảm giá không tồn tại'
                voucher_message_type = 'text-danger'

    booking_form = BookingForm(
        initial={
            'booking_date': selected_date,
            'voucher_code': voucher_code
        },
        time_slot_choices=time_slot_choices
    )

    if request.method == 'POST':
        booking_form = BookingForm(
            request.POST, time_slot_choices=time_slot_choices)
        if booking_form.is_valid():
            booking_date = booking_form.cleaned_data['booking_date']
            time_slot_id = booking_form.cleaned_data['time_slot']
            voucher_code = booking_form.cleaned_data['voucher_code']
            note = booking_form.cleaned_data['note']

            try:
                pitch_time_slot = PitchTimeSlot.objects.select_related(
                    'time_slot').get(id=time_slot_id, pitch=pitch)

                booking = Booking(
                    user=request.user,
                    pitch=pitch,
                    time_slot=pitch_time_slot,
                    booking_date=booking_date,
                    note=note
                )

                if voucher_code:
                    is_valid_format, error_message = validate_voucher_code(
                        voucher_code)

                    if is_valid_format:
                        voucher_code_clean = voucher_code.strip().upper()
                        try:
                            voucher = Voucher.objects.get(
                                code=voucher_code_clean)
                            if voucher.is_valid():
                                booking.voucher = voucher
                            else:
                                messages.warning(
                                    request, 'Mã giảm giá không hợp lệ, đặt sân không áp dụng giảm giá.')
                        except Voucher.DoesNotExist:
                            messages.warning(
                                request, 'Mã giảm giá không tồn tại, đặt sân không áp dụng giảm giá.')
                    else:
                        messages.warning(
                            request, f'{error_message}, đặt sân không áp dụng giảm giá.')

                booking.save()
                messages.success(
                    request, f'Đặt sân thành công! Mã đặt sân: #{booking.id}')
                logger.info(
                    f"Booking created: #{booking.id} by user {request.user.username}")
                return redirect('pitch_list')

            except (PitchTimeSlot.DoesNotExist, ValueError) as e:
                logger.error(f"Error creating booking", exc_info=True)
                messages.error(
                    request, 'Có lỗi xảy ra khi đặt sân. Vui lòng thử lại.')

    context = {
        'pitch': pitch,
        'selected_date': selected_date,
        'available_time_slots': available_time_slots,
        'voucher_code': voucher_code,
        'voucher_message': voucher_message,
        'voucher_message_type': voucher_message_type,
        'today': date.today().isoformat(),
        'date_form': date_form,
        'booking_form': booking_form,
        'default_pitch_image': constants.DEFAULT_PITCH_IMAGE,
    }

    return render(request, 'user/book_pitch.html', context)


@login_required(login_url='login')
def favorite_list(request):
    favorites = Favorite.objects.filter(user=request.user).select_related(
        'pitch',
        'pitch__facility',
        'pitch__pitch_type'
    )

    for favorite in favorites:
        favorite.pitch.is_favorited = True

    context = {
        'favorites': favorites,
        'is_user': request.user.role == constants.ROLE_USER,
        'default_pitch_image': constants.DEFAULT_PITCH_IMAGE,
    }
    return render(request, 'user/favorite_list.html', context)


@login_required(login_url='login')
@require_POST
def toggle_favorite(request, pitch_id):
    pitch = get_object_or_404(Pitch, id=pitch_id)
    
    favorite, created = Favorite.objects.get_or_create(
        user=request.user,
        pitch=pitch
    )

    if not created:
        favorite.delete()
        is_favorited = False
    else:
        is_favorited = True

    if 'application/json' in request.headers.get('Accept', ''):
        return JsonResponse({
            'success': True,
            'is_favorited': is_favorited,
            'message': 'Đã thêm vào yêu thích' if is_favorited else 'Đã xóa khỏi yêu thích'
        })

    return redirect('pitch_list')


@login_required
@require_POST
def add_review(request, pitch_id):
    pitch = get_object_or_404(Pitch, id=pitch_id)

    # Check if user has booked this pitch (CONFIRMED status)
    has_booked = Booking.objects.filter(
        user=request.user,
        pitch=pitch,
        status=BookingStatus.CONFIRMED
    ).exists()

    if not has_booked:
        messages.error(request, constants.ERR_REVIEW_ONLY_AFTER_BOOKING)
        return redirect('user_booking_create', pitch_id=pitch_id)

    form = ReviewForm(request.POST)
    if form.is_valid():
        review = form.save(commit=False)
        review.user = request.user
        review.pitch = pitch
        review.save()
        messages.success(request, constants.MSG_REVIEW_CREATED)
    else:
        messages.error(request, "Lỗi khi gửi đánh giá. Vui lòng kiểm tra lại.")

    return redirect('user_booking_create', pitch_id=pitch_id)
