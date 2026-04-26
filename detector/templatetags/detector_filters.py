"""
Custom template filters for the detector app.
"""
from django import template

register = template.Library()


@register.filter
def pct(value):
    """
    Convert a 0-1 ratio to a 0-100 percentage value.

    Usage: {{ confidence|pct|floatformat:1 }}%
    """
    try:
        return float(value) * 100
    except (ValueError, TypeError):
        return 0
