"""Normalized immutable entities. All money is integer USD cents."""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from .config import MAX_ORDERS, MAX_PRODUCTS, STATUSES


class ValidationError(ValueError):
    """Invalid external payload or dataset."""


def cents(value: object) -> int:
    if isinstance(value, bool):
        raise ValidationError('Money must be numeric.')
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or not 0 <= amount <= 1_000_000:
            raise ValidationError('Money must be finite and between 0 and 1,000,000 USD.')
        return int((amount * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValidationError('Invalid money amount.') from exc


def money_valid(value: int) -> bool:
    return type(value) is int and 0 <= value <= 100_000_000


@dataclass(frozen=True)
class Product:
    product_id: int
    title: str
    category: str
    unit_price: int


@dataclass(frozen=True)
class Customer:
    customer_id: str
    display_name: str


@dataclass(frozen=True)
class Order:
    order_id: str
    customer_id: str
    order_date: datetime
    status: str
    shipping_fee: int
    discount_amount: int


@dataclass(frozen=True)
class OrderItem:
    order_id: str
    product_id: int
    quantity: int
    unit_price_at_purchase: int


@dataclass(frozen=True)
class Dataset:
    products: tuple[Product, ...]
    customers: tuple[Customer, ...]
    orders: tuple[Order, ...]
    items: tuple[OrderItem, ...]

    def validate(self) -> None:
        if not 1 <= len(self.products) <= MAX_PRODUCTS or len(self.orders) > MAX_ORDERS:
            raise ValidationError('Dataset exceeds configured bounds or has no products.')
        for rows, key in ((self.products, 'product_id'), (self.customers, 'customer_id'), (self.orders, 'order_id')):
            ids = [getattr(row, key) for row in rows]
            if len(set(ids)) != len(ids) or any(not x for x in ids):
                raise ValidationError(f'Duplicate or empty {key}.')
        products = {p.product_id for p in self.products}
        customers = {c.customer_id for c in self.customers}
        orders = {o.order_id for o in self.orders}
        if len(self.customers) > MAX_ORDERS or len(self.items) > MAX_ORDERS * 5:
            raise ValidationError('Too many customers or line items.')
        for p in self.products:
            if type(p.product_id) is not int or p.product_id <= 0 or not money_valid(p.unit_price):
                raise ValidationError('Invalid product ID or price.')
            if not isinstance(p.title, str) or not 1 <= len(p.title.strip()) <= 200 or not isinstance(p.category, str) or not 1 <= len(p.category.strip()) <= 100:
                raise ValidationError('Invalid product title or category.')
        totals = dict.fromkeys(orders, 0)
        seen = set()
        for item in self.items:
            key = (item.order_id, item.product_id)
            if key in seen or item.order_id not in orders or item.product_id not in products:
                raise ValidationError('Invalid or duplicate order-item relationship.')
            seen.add(key)
            if type(item.quantity) is not int or not 1 <= item.quantity <= 1000 or not money_valid(item.unit_price_at_purchase):
                raise ValidationError('Invalid quantity or purchase price.')
            totals[item.order_id] += item.quantity * item.unit_price_at_purchase
        for order in self.orders:
            if order.customer_id not in customers or order.status not in STATUSES:
                raise ValidationError('Invalid customer reference or status.')
            if not isinstance(order.order_date, datetime) or order.order_date.tzinfo is None or order.order_date.utcoffset() is None:
                raise ValidationError('Order dates must be timezone-aware datetimes.')
            if not money_valid(order.shipping_fee) or not money_valid(order.discount_amount):
                raise ValidationError('Invalid order money.')
            if not any(key[0] == order.order_id for key in seen) or order.discount_amount > totals[order.order_id]:
                raise ValidationError('Order must have items and discount cannot exceed merchandise value.')
