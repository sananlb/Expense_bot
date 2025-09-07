"""
Django template filters for displaying multilingual categories
"""
from django import template
from django.utils.safestring import mark_safe
from bot.utils.category_helpers import get_category_display_name

register = template.Library()


@register.filter(name='category_display')
def category_display(category, language_code='ru'):
    """
    Display category name in the specified language
    
    Usage in templates:
        {{ expense.category|category_display }}
        {{ expense.category|category_display:'en' }}
        {{ income.category|category_display:user.language_code }}
    """
    if not category:
        return '—'
    
    return get_category_display_name(category, language_code)


@register.filter(name='category_display_html')
def category_display_html(category, language_code='ru'):
    """
    Display category name with icon in HTML format
    
    Usage in templates:
        {{ expense.category|category_display_html }}
        {{ expense.category|category_display_html:'en' }}
    """
    if not category:
        return mark_safe('<span>—</span>')
    
    display_name = get_category_display_name(category, language_code)
    
    # Wrap icon in a span for styling if needed
    parts = display_name.split(' ', 1)
    if len(parts) == 2 and parts[0]:
        # Check if first part is likely an emoji/icon
        if ord(parts[0][0]) > 127:  # Non-ASCII character, likely emoji
            html = f'<span class="category-icon">{parts[0]}</span> <span class="category-name">{parts[1]}</span>'
        else:
            html = f'<span class="category-full">{display_name}</span>'
    else:
        html = f'<span class="category-full">{display_name}</span>'
    
    return mark_safe(html)


@register.simple_tag
def category_list(profile, category_type='expense', language_code='ru'):
    """
    Get list of categories for a profile
    
    Usage in templates:
        {% category_list profile 'expense' 'ru' as expense_categories %}
        {% for cat in expense_categories %}
            {{ cat }}
        {% endfor %}
    """
    from expenses.models import ExpenseCategory, IncomeCategory
    
    if category_type == 'expense':
        categories = ExpenseCategory.objects.filter(
            profile=profile, 
            is_active=True
        ).order_by('name')
    else:
        categories = IncomeCategory.objects.filter(
            profile=profile, 
            is_active=True
        ).order_by('name')
    
    return [
        get_category_display_name(cat, language_code) 
        for cat in categories
    ]


@register.inclusion_tag('expenses/category_select.html')
def category_select(profile, selected=None, category_type='expense', language_code='ru'):
    """
    Render a select dropdown with categories
    
    Usage in templates:
        {% category_select profile selected_category 'expense' 'ru' %}
    """
    from expenses.models import ExpenseCategory, IncomeCategory
    
    if category_type == 'expense':
        categories = ExpenseCategory.objects.filter(
            profile=profile, 
            is_active=True
        ).order_by('name')
    else:
        categories = IncomeCategory.objects.filter(
            profile=profile, 
            is_active=True
        ).order_by('name')
    
    category_choices = []
    for cat in categories:
        display_name = get_category_display_name(cat, language_code)
        category_choices.append({
            'id': cat.id,
            'display_name': display_name,
            'selected': cat.id == selected.id if selected else False
        })
    
    return {
        'categories': category_choices,
        'category_type': category_type
    }