from django import forms 
from django.contrib.auth.forms import UserCreationForm 
from django.contrib.auth.password_validation import validate_password 
from django.core.exceptions import ValidationError 
from .models import User, Review 
from datetime import date 
import re 

class SignUpForm(UserCreationForm): 
    email = forms.EmailField(required=True) 
    full_name = forms.CharField(required=True, label="Họ và tên") 
    phone_number = forms.CharField(required=False, label="Số điện thoại") 

    class Meta: 
        model = User 
        fields = ('username', 'email', 'full_name', 'phone_number', 'password1', 'password2') 

    def __init__(self, *args, **kwargs): 
        super().__init__(*args, **kwargs) 
        self.fields['password1'].help_text = ( 
            "Mật khẩu phải có ít nhất 8 ký tự và chứa ít nhất 3 loại: " 
            "chữ thường, chữ hoa, số, ký tự đặc biệt" 
        ) 
        self.fields['password2'].label = "Xác nhận mật khẩu" 

    def validate_password_strength(self, password): 
        errors = [] 
        if len(password) < 8: 
            errors.append("Mật khẩu phải có ít nhất 8 ký tự.") 
        
        has_lower = bool(re.search(r'[a-z]', password)) 
        has_upper = bool(re.search(r'[A-Z]', password)) 
        has_digit = bool(re.search(r'\d', password)) 
        has_special = bool(re.search(r'[!@#$%^&*(),.?":{}|<>]', password)) 
        
        char_type_count = sum([has_lower, has_upper, has_digit, has_special]) 
        
        if char_type_count < 3: 
            errors.append("Mật khẩu phải chứa ít nhất 3 trong các loại sau: chữ thường, chữ hoa, số, ký tự đặc biệt.")         
        return errors 

    def clean_password1(self): 
        password1 = self.cleaned_data.get('password1') 
        if password1: 
            errors = self.validate_password_strength(password1) 
            if errors: 
                raise ValidationError(errors) 
        return password1 

    def clean(self): 
        cleaned_data = super().clean()         
        return cleaned_data 

    def save(self, commit=True): 
        user = super().save(commit=False) 
        user.email = self.cleaned_data["email"] 
        user.full_name = self.cleaned_data["full_name"] 
        user.phone_number = self.cleaned_data.get("phone_number", "") 
        user.role = "User" 
        user.is_active = False 
        
        if commit: 
            user.save() 
        return user 

class BookingForm(forms.Form): 
    booking_date = forms.DateField( 
        required=True, 
        label="Ngày đặt sân", 
        widget=forms.DateInput(attrs={ 
            'type': 'date', 
            'class': 'form-control form-control-lg', 
            'min': 'today' 
        }) 
    ) 
    
    time_slot = forms.ChoiceField( 
        required=True, 
        label="Khung giờ", 
        widget=forms.RadioSelect(attrs={'class': 'btn-check'}) 
    ) 
    
    voucher_code = forms.CharField( 
        required=False, 
        label="Mã giảm giá", 
        widget=forms.TextInput(attrs={ 
            'class': 'form-control', 
            'placeholder': 'Nhập mã giảm giá' 
        }) 
    ) 
    
    note = forms.CharField( 
        required=False, 
        label="Ghi chú", 
        widget=forms.Textarea(attrs={ 
            'class': 'form-control', 
            'rows': 3, 
            'placeholder': 'Nhập ghi chú của bạn...' 
        }) 
    ) 
    
    def __init__(self, *args, **kwargs): 
        time_slot_choices = kwargs.pop('time_slot_choices', []) 
        super().__init__(*args, **kwargs) 
        
        if not time_slot_choices: 
            self.fields['time_slot'].choices = [('', 'Không có khung giờ khả dụng')] 
            self.fields['time_slot'].required = False 
            self.fields['time_slot'].widget.attrs['disabled'] = True 
        else: 
            self.fields['time_slot'].choices = time_slot_choices 
        
        if 'booking_date' in self.initial: 
            self.fields['booking_date'].widget.attrs['value'] = self.initial['booking_date'] 
    
    def clean_booking_date(self): 
        booking_date = self.cleaned_data.get('booking_date') 
        if booking_date and booking_date < date.today(): 
            raise forms.ValidationError("Không thể đặt sân trong quá khứ.") 
        return booking_date 
    
    def clean(self): 
        cleaned_data = super().clean() 
        time_slot = cleaned_data.get('time_slot') 
        
        if self.fields['time_slot'].choices and self.fields['time_slot'].choices[0][0] != '': 
            if not time_slot: 
                raise forms.ValidationError({ 
                    'time_slot': 'Vui lòng chọn khung giờ.' 
                }) 
        
        return cleaned_data 

class DateSelectionForm(forms.Form): 
    booking_date = forms.DateField( 
        required=True, 
        label="Chọn ngày đặt sân", 
        widget=forms.DateInput(attrs={ 
            'type': 'date', 
            'class': 'form-control form-control-lg', 
            'min': 'today' 
        }) 
    ) 
    
    def clean_booking_date(self): 
        booking_date = self.cleaned_data.get('booking_date') 
        if booking_date and booking_date < date.today(): 
            raise forms.ValidationError("Không thể đặt sân trong quá khứ.") 
        return booking_date 

class ReviewForm(forms.ModelForm): 
    rating = forms.IntegerField( 
        required=True, 
        label="Đánh giá", 
        min_value=1, 
        max_value=5, 
        widget=forms.NumberInput(attrs={ 
            'type': 'range', 
            'class': 'form-range', 
            'min': '1', 
            'max': '5', 
            'id': 'ratingInput' 
        }) 
    ) 
    
    content = forms.CharField( 
        required=True, 
        label="Nội dung đánh giá", 
        min_length=10, 
        widget=forms.Textarea(attrs={ 
            'class': 'form-control', 
            'rows': 4, 
            'placeholder': 'Chia sẻ trải nghiệm của bạn về sân (tối thiểu 10 ký tự)...' 
        }) 
    ) 
    
    class Meta: 
        model = Review 
        fields = ['rating', 'content'] 
    
    def clean_content(self): 
        content = self.cleaned_data.get('content') 
        if content and len(content.strip()) < 10: 
            raise forms.ValidationError("Nội dung đánh giá phải có ít nhất 10 ký tự.") 
        return content
    