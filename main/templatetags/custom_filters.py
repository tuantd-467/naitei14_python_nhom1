from django import template
from urllib.parse import urlencode

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get item from dictionary by key"""
    return dictionary.get(key)

@register.filter
def param_replace(value, arg):
    """Replace or add a parameter in the query string"""
    if not isinstance(value, dict):
        return value
    
    params = value.copy()
    
    if '=' in arg:
        updates = arg.split('=', 1)  
        key = updates[0]
        new_value = updates[1] if len(updates) > 1 else ''
        
        new_value = str(new_value).strip() if new_value else ''
        
        if isinstance(params.get(key), list):
            params[key] = [new_value] if new_value else []
        else:
            if new_value:
                params[key] = new_value
            else:
                params.pop(key, None)
    
    return urlencode(params, doseq=True)

@register.filter
def param_remove(value, key_to_remove):
    """
    Remove a GET parameter from query string
    Usage: {{ request_get|param_remove:"q" }}
    """
    if not isinstance(value, dict):
        return value
    
    params = value.copy()
    params.pop(key_to_remove, None)
    return urlencode(params, doseq=True)

@register.filter
def price_range_display(value):
    """Display price range in human readable format"""
    if isinstance(value, list):
        value = value[0] if value else ''
    
    price_ranges = {
        '0-100000': 'Dưới 100,000đ/giờ',
        '100000-200000': '100,000đ - 200,000đ/giờ',
        '200000-300000': '200,000đ - 300,000đ/giờ',
        '300000': 'Trên 300,000đ/giờ'
    }
    return price_ranges.get(value, value)

@register.filter
def get_single_value(value):
    """Get single value from potentially list value"""
    if isinstance(value, list):
        return value[0] if value else ''
    return value