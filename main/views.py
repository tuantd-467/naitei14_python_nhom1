from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from .forms import SignUpForm, BookingForm, DateSelectionForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Exists, OuterRef
from django.contrib import messages
from datetime import datetime, date
import re

from .models import Booking, Facility, Pitch, PitchTimeSlot, PitchType, Voucher, BookingStatus
from . import constants

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


def sign_up(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = SignUpForm()
    return render(request, 'registration/sign-up.html', {'form': form})

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
    
    has_filters = any([search_query, pitch_type_filter, price_range_filter, booking_date_filter])
    
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

@login_required(login_url='login')
def book_pitch(request, pitch_id):
    if request.user.role != constants.ROLE_USER:
        return HttpResponseForbidden("Bạn không có quyền đặt sân!")

    pitch = get_object_or_404(Pitch, id=pitch_id)
    
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
            
            print(f"DEBUG: Total PitchTimeSlots for pitch {pitch.id}: {all_pitch_time_slots.count()}")
            
            if all_pitch_time_slots.count() == 0:
                print("WARNING: Không có PitchTimeSlot nào được tạo cho sân này!")
                print("Bạn cần tạo dữ liệu PitchTimeSlot qua Django Admin hoặc shell")
            
            for pitch_time_slot in all_pitch_time_slots:
                print(f"DEBUG: Checking slot {pitch_time_slot.time_slot.name}")
                is_available = pitch_time_slot.is_available_on_date(booking_date)
                print(f"DEBUG: Slot {pitch_time_slot.time_slot.name} available: {is_available}")
                
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
            
            print(f"DEBUG: Available time slots: {len(available_time_slots)}")
        except ValueError:
            selected_date = ''
    
    # Validate and check voucher code
    voucher_message = ''
    voucher_message_type = 'text-muted'
    if voucher_code:
        # Validate voucher code format
        is_valid_format, error_message = validate_voucher_code(voucher_code)
        
        if not is_valid_format:
            voucher_message = error_message
            voucher_message_type = 'text-danger'
        else:
            # Sanitize and check voucher in database
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
                
                # Validate and apply voucher if provided
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
                
                messages.success(request, f'Đặt sân thành công! Mã đặt sân: #{booking.id}')
                return redirect('pitch_list')
                
            except (PitchTimeSlot.DoesNotExist, ValueError) as e:
                messages.error(request, 'Có lỗi xảy ra khi đặt sân. Vui lòng thử lại.')
                print(f"ERROR: {e}")
    
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
