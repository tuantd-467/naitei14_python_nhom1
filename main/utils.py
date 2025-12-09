from django.core.mail import send_mail 
from django.conf import settings 
from datetime import timedelta 
from django.utils import timezone 
import secrets 
import string 
import textwrap

def generate_activation_token(): 
    return secrets.token_urlsafe(24)

def send_activation_email(user, request): 
    user.activation_token = generate_activation_token() 
    user.activation_expiry = timezone.now() + timedelta( 
        hours=settings.ACTIVATION_TOKEN_EXPIRY_HOURS 
    ) 
    user.save() 
    
    activation_link = request.build_absolute_uri( 
        f'/activate/{user.activation_token}/' 
    ) 
    
    subject = 'Xác thực tài khoản của bạn' 
    message = textwrap.dedent(f""" 
        Xin chào {user.full_name}, 
        
        Vui lòng nhấp vào liên kết dưới đây để xác thực tài khoản của bạn: 
        {activation_link} 
        
        Liên kết này sẽ hết hạn sau {settings.ACTIVATION_TOKEN_EXPIRY_HOURS} giờ. 
        
        Nếu bạn không tạo tài khoản này, vui lòng bỏ qua email này. 
        
        Trân trọng, 
        Đội ngũ hỗ trợ 
    """).strip() 
    
    html_message = textwrap.dedent(f""" 
        <html> 
            <body> 
                <p>Xin chào <strong>{user.full_name}</strong>,</p> 
                <p>Vui lòng nhấp vào liên kết dưới đây để xác thực tài khoản của bạn:</p> 
                <p><a href="{activation_link}">Xác thực tài khoản</a></p> 
                <p>Liên kết này sẽ hết hạn sau <strong>{settings.ACTIVATION_TOKEN_EXPIRY_HOURS} giờ</strong>.</p> 
                <p>Nếu bạn không tạo tài khoản này, vui lòng bỏ qua email này.</p> 
                <p>Trân trọng,<br>Đội ngũ hỗ trợ</p> 
            </body> 
        </html> 
    """).strip() 
    
    send_mail( 
        subject, 
        message, 
        settings.DEFAULT_FROM_EMAIL, 
        [user.email], 
        html_message=html_message, 
        fail_silently=False, 
    ) 

def verify_activation_token(token): 
    from .models import User 
    try: 
        user = User.objects.get(activation_token=token) 
        
        if user.activation_expiry and timezone.now() > user.activation_expiry: 
            return False, "Token đã hết hạn. Vui lòng đăng ký lại." 
        
        user.is_active = True 
        user.activation_token = None 
        user.activation_expiry = None 
        user.save() 
        
        return True, "Tài khoản đã được kích hoạt thành công!" 
    except User.DoesNotExist: 
        return False, "Token không hợp lệ."
    