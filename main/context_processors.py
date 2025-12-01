def user_role_context(request):
    """
    Context processor để tự động thêm thông tin role của user vào mọi template
    """
    if request.user.is_authenticated:
        return {
            'user_role': request.user.role,
            'is_admin': request.user.role == "Admin",
            'is_user': request.user.role == "User"
        }
    return {
        'user_role': None,
        'is_admin': False,
        'is_user': False
    }
    