from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Template filter para acceder a valores de diccionario con claves dinámicas
    Uso: {{ dict|get_item:key }}
    """
    if dictionary is None:
        return 0
    
    # ⬅️ ESTA ES LA CORRECCIÓN CRÍTICA
    if not isinstance(dictionary, dict):
        return 0
    
    return dictionary.get(str(key), 0)

@register.filter
def mul(value, arg):
    """Multiplicar dos valores"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def div(value, arg):
    """Dividir dos valores"""
    try:
        if float(arg) == 0:
            return 0
        return float(value) / float(arg)
    except (ValueError, TypeError):
        return 0