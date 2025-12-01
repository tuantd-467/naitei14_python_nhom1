from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User
from datetime import date

class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)
    full_name = forms.CharField(required=True, label="Họ và tên")
    phone_number = forms.CharField(required=False, label="Số điện thoại")

    class Meta:
        model = User
        fields = ('username', 'email', 'full_name', 'phone_number', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.full_name = self.cleaned_data["full_name"]
        user.phone_number = self.cleaned_data.get("phone_number", "")
        user.role = "User"
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
    