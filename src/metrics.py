"""Single financial calculation path for UI and exports; integer USD cents."""
from dataclasses import asdict, dataclass
from datetime import date, timezone
from .config import PAID_STATUSES, STATUSES
from .models import Dataset


@dataclass(frozen=True)
class Filters:
    start: date
    end: date
    statuses: tuple[str, ...] = STATUSES
    search: str = ''


def filter_dataset(data: Dataset, filters: Filters) -> Dataset:
    if filters.start > filters.end or any(s not in STATUSES for s in filters.statuses):
        raise ValueError('Invalid filter range or status.')
    orders = tuple(o for o in data.orders
                   if filters.start <= o.order_date.astimezone(timezone.utc).date() <= filters.end
                   and o.status in filters.statuses and filters.search.strip().casefold() in o.order_id.casefold())
    ids = {o.order_id for o in orders}
    return Dataset(data.products, data.customers, orders, tuple(i for i in data.items if i.order_id in ids))


def order_rows(data: Dataset) -> list[dict]:
    subtotals = dict.fromkeys((o.order_id for o in data.orders), 0)
    units = subtotals.copy()
    for item in data.items:
        subtotals[item.order_id] += item.quantity * item.unit_price_at_purchase
        units[item.order_id] += item.quantity
    result = []
    for order in data.orders:
        gmv = subtotals[order.order_id]
        charged = gmv - order.discount_amount + order.shipping_fee
        recognized = order.status in PAID_STATUSES
        result.append({**asdict(order), 'order_date': order.order_date.astimezone(timezone.utc).isoformat(),
                       'gmv': gmv, 'units': units[order.order_id],
                       'refunds': charged if order.status == 'refunded' else 0,
                       'net_sales': charged if recognized else 0})
    return result


def calculate(data: Dataset) -> dict[str, int]:
    rows = order_rows(data)
    paid = [r for r in rows if r['status'] in PAID_STATUSES]
    net = sum(r['net_sales'] for r in rows)
    count = len(paid)
    return {
        'gmv': sum(r['gmv'] for r in rows),
        'discounts': sum(r['discount_amount'] for r in paid),
        'shipping_fees': sum(r['shipping_fee'] for r in paid),
        'refunds': sum(r['refunds'] for r in rows),
        'cancelled_orders': sum(r['status'] == 'cancelled' for r in rows),
        'cancelled_gmv': sum(r['gmv'] for r in rows if r['status'] == 'cancelled'),
        'refunded_orders': sum(r['status'] == 'refunded' for r in rows),
        'paid_gmv': sum(r['gmv'] for r in paid),
        'net_sales': net, 'paid_order_count': count,
        'average_order_value': (net * 2 + count) // (2 * count) if count else 0,
        'units_sold': sum(r['units'] for r in paid), 'selected_order_count': len(rows),
    }


def daily_sales(data: Dataset, filters: Filters) -> list[dict]:
    from datetime import timedelta
    totals = {}
    for row in order_rows(data):
        day = row['order_date'][:10]
        totals[day] = totals.get(day, 0) + row['net_sales']
    result = []
    day = filters.start
    if (filters.end - day).days > 3660:
        raise ValueError('Date range exceeds 10 years.')
    while day <= filters.end:
        result.append({'date': day.isoformat(), 'net_sales': totals.get(day.isoformat(), 0)})
        day += timedelta(days=1)
    return result


def top_products(data: Dataset) -> list[dict]:
    """Allocate each paid order discount by largest remainder, stable product-ID ties.

    Product net revenue excludes shipping. Allocations sum exactly to the discount.
    """
    products = {p.product_id: p for p in data.products}
    grouped = {}
    for item in data.items:
        grouped.setdefault(item.order_id, []).append(item)
    totals = {}
    for order in data.orders:
        if order.status not in PAID_STATUSES:
            continue
        items = sorted(grouped[order.order_id], key=lambda i: i.product_id)
        amounts = [i.quantity * i.unit_price_at_purchase for i in items]
        subtotal = sum(amounts)
        allocations = [amount * order.discount_amount // subtotal if subtotal else 0 for amount in amounts]
        remainders = [amount * order.discount_amount % subtotal if subtotal else 0 for amount in amounts]
        leftover = order.discount_amount - sum(allocations)
        for index in sorted(range(len(items)), key=lambda k: (-remainders[k], items[k].product_id))[:leftover]:
            allocations[index] += 1
        for item, amount, discount in zip(items, amounts, allocations):
            product = products[item.product_id]
            row = totals.setdefault(item.product_id, {'product_id': product.product_id, 'title': product.title,
                                                      'category': product.category, 'units_sold': 0, 'net_revenue': 0})
            row['units_sold'] += item.quantity
            row['net_revenue'] += amount - discount
    return sorted(totals.values(), key=lambda r: (-r['net_revenue'], r['product_id']))


def status_distribution(data: Dataset) -> list[dict]:
    return [{'status': status, 'orders': sum(o.status == status for o in data.orders)} for status in STATUSES]
