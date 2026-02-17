from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError

def validate_positive_decimal(value, field_name):
    try:
        decimal_val = Decimal(str(value))
        if decimal_val <= 0:
            raise ValidationError(f"{field_name} must be positive")
        return decimal_val
    except (ValueError, InvalidOperation):
        raise ValidationError(f"Invalid {field_name}")
