"""Reproducible fictional commerce data, independent of today's date."""
from datetime import datetime, timedelta, timezone
import json
import random
from .config import ROOT, SEED, MAX_ORDERS
from .models import Customer, Dataset, Order, OrderItem, Product
from .transform import parse_products


def offline_products() -> tuple[Product, ...]:
    return parse_products(json.loads((ROOT / 'assets/products.json').read_text()))


def generate_dataset(products: tuple[Product, ...] | None = None, *, seed: int = SEED,
                     order_count: int = 240) -> Dataset:
    catalog = offline_products() if products is None else tuple(sorted(products, key=lambda p: p.product_id))
    if not catalog or not 1 <= order_count <= MAX_ORDERS:
        raise ValueError('A nonempty catalog and 1–5000 orders are required.')
    rng = random.Random(seed)
    customers = tuple(Customer(f'DEMO-C{i:03}', f'Demo Customer {i:03}') for i in range(1, 41))
    orders, items = [], []
    start = datetime(2026, 7, 1, tzinfo=timezone.utc)
    for i in range(order_count):
        oid = f'DEMO-{i + 1:05}'
        subtotal = 0
        for product in rng.sample(catalog, k=rng.randint(1, min(4, len(catalog)))):
            quantity = rng.randint(1, 4)
            # Fictional historical prices differ from current catalog prices.
            price = (product.unit_price * rng.choice((90, 95, 100, 105)) + 50) // 100
            items.append(OrderItem(oid, product.product_id, quantity, price))
            subtotal += quantity * price
        status = rng.choices(('paid', 'shipped', 'completed', 'pending', 'cancelled', 'refunded'),
                             weights=(15, 20, 45, 8, 7, 5))[0]
        discount = (subtotal * rng.choice((0, 0, 5, 10, 15)) + 50) // 100
        orders.append(Order(oid, rng.choice(customers).customer_id,
                            start + timedelta(days=rng.randrange(92), hours=rng.randrange(24), minutes=rng.randrange(60)),
                            status, 0 if subtotal >= 15000 else 599, discount))
    data = Dataset(catalog, customers, tuple(sorted(orders, key=lambda o: (o.order_date, o.order_id))), tuple(items))
    data.validate()
    return data
