"""Validate and minimize external product payloads before use."""
from .models import Product, ValidationError, cents
from .config import MAX_PRODUCTS


def parse_products(payload: object) -> tuple[Product, ...]:
    if not isinstance(payload, dict) or not isinstance(payload.get('products'), list):
        raise ValidationError('API response must contain a products list.')
    rows = payload['products']
    if len(rows) > MAX_PRODUCTS:
        raise ValidationError('Too many products in response.')
    result = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValidationError('Product must be an object.')
        pid, title, category = row.get('id'), row.get('title'), row.get('category')
        if type(pid) is not int or pid <= 0 or pid in seen:
            raise ValidationError('Product IDs must be unique positive integers.')
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 200:
            raise ValidationError('Invalid product title.')
        if not isinstance(category, str) or not 1 <= len(category.strip()) <= 100:
            raise ValidationError('Invalid category.')
        result.append(Product(pid, title.strip(), category.strip(), cents(row.get('price'))))
        seen.add(pid)
    return tuple(result)
