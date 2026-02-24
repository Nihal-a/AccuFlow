from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from django.db.models import Max

def validate_positive_decimal(value, field_name):
    try:
        decimal_val = Decimal(str(value))
        if decimal_val <= 0:
            raise ValidationError(f"{field_name} must be positive")
        return decimal_val
    except (ValueError, InvalidOperation):
        raise ValidationError(f"Invalid {field_name}")

def get_next_id(model_class, field_name, client, prefix='ID-', separator='-'):
    last_item = model_class.objects.filter(client=client, is_active=True).order_by(field_name).last()
    if last_item and getattr(last_item, field_name):
        try:
            val = str(getattr(last_item, field_name))
            if separator in val:
                pref, num = val.rsplit(separator, 1)
                return f"{pref}{separator}{int(num) + 1}"
            elif val.isdigit():
                return str(int(val) + 1)
            else:
                return f"{prefix}1"
        except (ValueError, IndexError):
            return f"{prefix}1"
    return f"{prefix}1"

def get_next_sale_no(client):
    from core.models import Sales
    last_sale = Sales.objects.filter(is_active=True, client=client).order_by('-sale_no').first()
    if last_sale and last_sale.sale_no and str(last_sale.sale_no).isdigit():
        return int(last_sale.sale_no) + 1
    return 1

def get_next_purchase_no(client):
    from core.models import Purchases
    last = Purchases.objects.filter(is_active=True, client=client).order_by('-purchase_no').first()
    if last and last.purchase_no and str(last.purchase_no).isdigit():
        return int(last.purchase_no) + 1
    return 1

def get_next_id_generic(model_name, client):
    from core.models import Customers, Suppliers, Expenses, Godowns, CashBanks, Collectors, Purchases, Sales, Commissions, NSDs, Cashs, StockTransfers
    
    if model_name == 'Customers':
        return get_next_id(Customers, 'customerId', client, 'C-')
    elif model_name == 'Suppliers':
        return get_next_id(Suppliers, 'supplierId', client, 'S-')
    elif model_name == 'Expenses':
        return get_next_id(Expenses, 'expenseId', client, 'E-')
    elif model_name == 'Godowns':
        return get_next_id(Godowns, 'godownId', client, 'G-')
    elif model_name == 'CashBanks':
        return get_next_id(CashBanks, 'cashbankId', client, 'CB-')
    elif model_name == 'Collectors':
        return get_next_id(Collectors, 'collectorId', client, 'COL-')
    elif model_name == 'Purchases':
        return str(get_next_purchase_no(client))
    elif model_name == 'Sales':
        return str(get_next_sale_no(client))
    elif model_name == 'Commissions':
        return get_next_id(Commissions, 'commission_no', client, 'COM-')
    elif model_name == 'NSDs':
        return get_next_id(NSDs, 'nsd_no', client, 'NSD-')
    elif model_name == 'Cashs':
        return get_next_id(Cashs, 'cash_no', client, 'CASH-')
    elif model_name == 'StockTransfers':
        return get_next_id(StockTransfers, 'transfer_no', client, 'ST-')
    return None
