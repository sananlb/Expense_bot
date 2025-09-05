from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def admin_required(view_func):
    """Декоратор для проверки прав администратора"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Необходима авторизация')
            return redirect('admin:login')
        
        if not (request.user.is_superuser or request.user.is_staff):
            messages.error(request, 'У вас нет прав доступа к этой странице')
            return redirect('admin:index')
        
        return view_func(request, *args, **kwargs)
    
    return wrapper