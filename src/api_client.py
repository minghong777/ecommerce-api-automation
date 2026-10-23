"""Bounded, retryable, paginated DummyJSON integration; no credentials."""
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import time
from typing import Callable
import httpx
from .config import API_URL, MAX_PRODUCTS, MAX_RESPONSE_BYTES
from .models import Product, ValidationError
from .transform import parse_products


class APIError(RuntimeError):
    """Safe, user-facing API failure."""


@dataclass(frozen=True)
class FetchResult:
    products: tuple[Product, ...]
    fetched_at: datetime
    requests: int
    total: int


def fetch_products(client: httpx.Client | None = None, *, page_size: int = 50,
                   max_products: int = MAX_PRODUCTS,
                   sleep: Callable[[float], None] = time.sleep) -> FetchResult:
    if not 1 <= page_size <= 100 or not 1 <= max_products <= MAX_PRODUCTS:
        raise ValueError('Invalid pagination bounds.')
    if client is None:
        with httpx.Client(timeout=httpx.Timeout(8.0, connect=4.0), follow_redirects=False) as owned:
            return fetch_products(owned, page_size=page_size, max_products=max_products, sleep=sleep)
    products: list[Product] = []
    requests = 0
    total = None
    seen: set[int] = set()
    while total is None or len(products) < min(total, max_products):
        limit = min(page_size, max_products - len(products))
        for attempt in range(3):
            requests += 1
            try:
                with client.stream('GET', API_URL, params={'limit': limit, 'skip': len(products),
                                   'select': 'id,title,category,price'}, timeout=8.0) as response:
                    if response.status_code in {408, 429, 500, 502, 503, 504}:
                        if attempt == 2:
                            raise APIError('Product service is temporarily unavailable after 3 attempts. Use offline products.')
                        sleep(0.25 * 2 ** attempt)
                        continue
                    response.raise_for_status()
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body) > MAX_RESPONSE_BYTES:
                            raise APIError('API response exceeded the safe size limit.')
                payload = json.loads(body)
                rows = parse_products(payload)
                reported_total = payload.get('total')
                if type(reported_total) is not int or not 1 <= reported_total <= 100_000:
                    raise ValidationError('Invalid API total.')
                if payload.get('skip') != len(products) or type(payload.get('skip')) is not int:
                    raise ValidationError('Unexpected pagination offset.')
                if total is not None and total != reported_total:
                    raise ValidationError('Catalog changed during pagination; retry fetch.')
                total = reported_total
                if not rows or len(rows) > limit or len(products) + len(rows) > total:
                    raise ValidationError('Incomplete or oversized API page.')
                if any(row.product_id in seen for row in rows):
                    raise ValidationError('Repeated product IDs across pages.')
                seen.update(row.product_id for row in rows)
                products.extend(rows)
                break
            except httpx.TransportError as exc:
                if attempt == 2:
                    raise APIError('Network connection failed after 3 attempts. Offline products remain available.') from exc
                sleep(0.25 * 2 ** attempt)
            except httpx.HTTPStatusError as exc:
                raise APIError(f'Product API returned HTTP {exc.response.status_code}.') from exc
            except (ValueError, UnicodeError) as exc:
                raise APIError('Product API returned an invalid payload.') from exc
    return FetchResult(tuple(products), datetime.now(timezone.utc), requests, total or 0)
