"""
Ledger helper — builds transaction lists for WhatsApp image generation.

Reuses the same query logic as customer_ledger & supplier_ledger views
to produce the exact same data the image.js generateTradeTable() expects.
"""

from decimal import Decimal
from datetime import datetime
from django.db.models import Q, Sum

from core.models import Purchases, Sales, NSDs, Cashs


def get_customer_ledger(customer, client, date_from=None, date_to=None):
    """
    Fetch ledger entries for a customer within optional date range.
    
    Returns:
        dict with 'opening_balance', 'transactions', 'closing_balance'
        
    Each transaction has: type, details, qty, rate, debit, credit, balance
    (matching what image.js generateTradeTable expects).
    """
    # Parse dates
    d_from = _parse_date(date_from)
    d_to = _parse_date(date_to)

    # Opening balance
    if d_from:
        opening_balance = _calc_customer_opening(customer, client, d_from)
    else:
        opening_balance = customer.open_debit - customer.open_credit

    # Collect transactions
    base_filter = Q(is_active=True, hold=False, client=client)
    date_filter = Q()
    if d_from:
        date_filter &= Q(date__gte=d_from)
    if d_to:
        date_filter &= Q(date__lte=d_to)

    ledger_items = []

    # Purchases (credit to customer)
    for p in Purchases.objects.filter(base_filter, date_filter, customer=customer):
        ledger_items.append({
            'date': p.date,
            'type': 'PR',
            'details': p.description or '',
            'qty': str(p.qty or ''),
            'rate': str(p.amount or ''),
            'credit': p.total_amount or Decimal('0'),
            'debit': Decimal('0'),
            'created_at': p.created_at,
        })

    # Sales (debit to customer)
    for s in Sales.objects.filter(base_filter, date_filter, customer=customer):
        ledger_items.append({
            'date': s.date,
            'type': 'SL',
            'details': s.description or '',
            'qty': str(s.qty or ''),
            'rate': str(s.amount or ''),
            'credit': Decimal('0'),
            'debit': s.total_amount or Decimal('0'),
            'created_at': s.created_at,
        })

    # NSDs — sender (credit)
    for n in NSDs.objects.filter(base_filter, date_filter, sender_customer=customer):
        ledger_items.append({
            'date': n.date,
            'type': 'NS',
            'details': n.description or '',
            'qty': str(n.qty or ''),
            'rate': str(n.sell_rate or ''),
            'credit': n.sell_amount or Decimal('0'),
            'debit': Decimal('0'),
            'created_at': n.created_at,
        })

    # NSDs — receiver (debit)
    for n in NSDs.objects.filter(base_filter, date_filter, receiver_customer=customer):
        ledger_items.append({
            'date': n.date,
            'type': 'NS',
            'details': n.description or '',
            'qty': str(n.qty or ''),
            'rate': str(n.purchase_rate or ''),
            'credit': Decimal('0'),
            'debit': n.purchase_amount or Decimal('0'),
            'created_at': n.created_at,
        })

    # Cash entries
    for c in Cashs.objects.filter(base_filter, date_filter, customer=customer):
        is_received = (c.transaction == 'Received')
        ledger_items.append({
            'date': c.date,
            'type': 'JL',
            'details': c.description or (c.cash_bank.name if c.cash_bank else ''),
            'qty': '',
            'rate': str(c.amount or ''),
            'credit': c.amount if is_received else Decimal('0'),
            'debit': c.amount if not is_received else Decimal('0'),
            'created_at': c.created_at,
        })

    # Sort by date
    ledger_items.sort(key=lambda x: (x['date'], x['created_at']))

    # Calculate running balance and clean up non-serializable fields
    running = opening_balance
    for item in ledger_items:
        d_val = item['debit'] or Decimal('0')
        c_val = item['credit'] or Decimal('0')
        running += (d_val - c_val)
        item['balance'] = str(running)
        item['debit'] = str(item['debit'])
        item['credit'] = str(item['credit'])
        # Remove non-JSON-serializable fields (only used for sorting)
        item.pop('date', None)
        item.pop('created_at', None)

    return {
        'opening_balance': str(opening_balance),
        'transactions': ledger_items,
        'closing_balance': str(running),
    }


def get_supplier_ledger(supplier, client, date_from=None, date_to=None):
    """
    Fetch ledger entries for a supplier within optional date range.
    Same structure as customer ledger.
    """
    d_from = _parse_date(date_from)
    d_to = _parse_date(date_to)

    if d_from:
        opening_balance = _calc_supplier_opening(supplier, client, d_from)
    else:
        opening_balance = supplier.open_debit - supplier.open_credit

    base_filter = Q(is_active=True, hold=False, client=client)
    date_filter = Q()
    if d_from:
        date_filter &= Q(date__gte=d_from)
    if d_to:
        date_filter &= Q(date__lte=d_to)

    ledger_items = []

    # Purchases (debit to supplier)
    for p in Purchases.objects.filter(base_filter, date_filter, supplier=supplier):
        ledger_items.append({
            'date': p.date,
            'type': 'PR',
            'details': p.description or '',
            'qty': str(p.qty or ''),
            'rate': str(p.amount or ''),
            'credit': Decimal('0'),
            'debit': p.total_amount or Decimal('0'),
            'created_at': p.created_at,
        })

    # Sales (credit to supplier)
    for s in Sales.objects.filter(base_filter, date_filter, supplier=supplier):
        ledger_items.append({
            'date': s.date,
            'type': 'SL',
            'details': s.description or '',
            'qty': str(s.qty or ''),
            'rate': str(s.amount or ''),
            'credit': s.total_amount or Decimal('0'),
            'debit': Decimal('0'),
            'created_at': s.created_at,
        })

    # NSDs — sender (debit to supplier)
    for n in NSDs.objects.filter(base_filter, date_filter, sender_supplier=supplier):
        ledger_items.append({
            'date': n.date,
            'type': 'NS',
            'details': n.description or '',
            'qty': str(n.qty or ''),
            'rate': str(n.sell_rate or ''),
            'credit': Decimal('0'),
            'debit': n.sell_amount or Decimal('0'),
            'created_at': n.created_at,
        })

    # NSDs — receiver (credit to supplier)
    for n in NSDs.objects.filter(base_filter, date_filter, receiver_supplier=supplier):
        ledger_items.append({
            'date': n.date,
            'type': 'NS',
            'details': n.description or '',
            'qty': str(n.qty or ''),
            'rate': str(n.purchase_rate or ''),
            'credit': n.purchase_amount or Decimal('0'),
            'debit': Decimal('0'),
            'created_at': n.created_at,
        })

    # Cash entries
    for c in Cashs.objects.filter(base_filter, date_filter, supplier=supplier):
        is_paid = (c.transaction == 'Paid')
        ledger_items.append({
            'date': c.date,
            'type': 'JL',
            'details': c.description or (c.cash_bank.name if c.cash_bank else ''),
            'qty': '',
            'rate': str(c.amount or ''),
            'credit': c.amount if is_paid else Decimal('0'),
            'debit': c.amount if not is_paid else Decimal('0'),
            'created_at': c.created_at,
        })

    ledger_items.sort(key=lambda x: (x['date'], x['created_at']))

    running = opening_balance
    for item in ledger_items:
        d_val = item['debit'] or Decimal('0')
        c_val = item['credit'] or Decimal('0')
        running += (d_val - c_val)
        item['balance'] = str(running)
        item['debit'] = str(item['debit'])
        item['credit'] = str(item['credit'])
        item.pop('date', None)
        item.pop('created_at', None)

    return {
        'opening_balance': str(opening_balance),
        'transactions': ledger_items,
        'closing_balance': str(running),
    }


# --- HELPERS ---

def _parse_date(date_str):
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _calc_customer_opening(customer, client, date_limit):
    base_filter = Q(is_active=True, hold=False, client=client, customer=customer, date__lt=date_limit)
    nsd_base = Q(is_active=True, hold=False, client=client, date__lt=date_limit)

    purchases_sum = Purchases.objects.filter(base_filter).aggregate(s=Sum('total_amount'))['s'] or Decimal('0')
    sales_sum = Sales.objects.filter(base_filter).aggregate(s=Sum('total_amount'))['s'] or Decimal('0')
    sender_sum = NSDs.objects.filter(nsd_base, sender_customer=customer).aggregate(s=Sum('sell_amount'))['s'] or Decimal('0')
    receiver_sum = NSDs.objects.filter(nsd_base, receiver_customer=customer).aggregate(s=Sum('purchase_amount'))['s'] or Decimal('0')
    cash_received = Cashs.objects.filter(base_filter, transaction="Received").aggregate(s=Sum('amount'))['s'] or Decimal('0')
    cash_paid = Cashs.objects.filter(base_filter, transaction="Paid").aggregate(s=Sum('amount'))['s'] or Decimal('0')

    transaction_balance = (sales_sum + receiver_sum + cash_paid) - (purchases_sum + sender_sum + cash_received)
    static_ob = customer.open_debit - customer.open_credit
    return static_ob + transaction_balance


def _calc_supplier_opening(supplier, client, date_limit):
    base_filter = Q(is_active=True, hold=False, client=client, supplier=supplier, date__lt=date_limit)
    nsd_base = Q(is_active=True, hold=False, client=client, date__lt=date_limit)

    purchases_sum = Purchases.objects.filter(base_filter).aggregate(s=Sum('total_amount'))['s'] or Decimal('0')
    sales_sum = Sales.objects.filter(base_filter).aggregate(s=Sum('total_amount'))['s'] or Decimal('0')
    sender_sum = NSDs.objects.filter(nsd_base, sender_supplier=supplier).aggregate(s=Sum('sell_amount'))['s'] or Decimal('0')
    receiver_sum = NSDs.objects.filter(nsd_base, receiver_supplier=supplier).aggregate(s=Sum('purchase_amount'))['s'] or Decimal('0')
    cash_received = Cashs.objects.filter(base_filter, transaction="Received").aggregate(s=Sum('amount'))['s'] or Decimal('0')
    cash_paid = Cashs.objects.filter(base_filter, transaction="Paid").aggregate(s=Sum('amount'))['s'] or Decimal('0')

    transaction_balance = (purchases_sum + sender_sum + cash_received) - (sales_sum + receiver_sum + cash_paid)
    static_ob = supplier.open_debit - supplier.open_credit
    return static_ob + transaction_balance
