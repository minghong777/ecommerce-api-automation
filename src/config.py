from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_URL = 'https://dummyjson.com/products'
MAX_PRODUCTS = 500
MAX_ORDERS = 5000
MAX_RESPONSE_BYTES = 2_000_000
MAX_EXPORT_BYTES = 10_000_000
STATUSES = ('paid', 'shipped', 'completed', 'pending', 'cancelled', 'refunded')
PAID_STATUSES = frozenset(('paid', 'shipped', 'completed'))
SEED = 20261022
