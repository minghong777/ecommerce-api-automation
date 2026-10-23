"""Official Sheets v4 REST adapter with owned-tab atomic snapshot replacement."""
from dataclasses import dataclass
from decimal import Decimal
import hashlib
import json
import random
import re
import time
from typing import Callable
import httpx
from .reports import ORDER_COLUMNS, TOP_COLUMNS

BASE_URL = 'https://sheets.googleapis.com/v4/spreadsheets'
OWNER_KEY = 'commerceflow_owner'
OWNER_VALUE = 'commerceflow_snapshot_v1'
MAX_BATCH_BYTES = 1_900_000


class SheetsError(RuntimeError):
    """Sanitized synchronization failure; never includes response bodies or tokens."""


@dataclass(frozen=True)
class SheetTargets:
    summary: str = 'CommerceFlow_Summary'
    orders: str = 'CommerceFlow_Orders'
    products: str = 'CommerceFlow_TopProducts'

    def validate(self) -> None:
        names = (self.summary, self.orders, self.products)
        if len(set(n.casefold() for n in names)) != 3:
            raise ValueError('Worksheet names must be distinct.')
        if any(not n.strip() or len(n) > 100 or re.search(r'[\[\]:*?/\\\x00-\x1f]', n) for n in names):
            raise ValueError('Invalid worksheet name.')


@dataclass(frozen=True)
class SyncPlan:
    tables: dict[str, list[list[str | int]]]
    digest: str

    def preview(self) -> dict:
        return {'mode': 'dry-run', 'remote_checked': False, 'writes_performed': False,
                'strategy': 'Atomic replacement of dedicated ownership-marked tabs; refuse unmanaged tabs.',
                'digest': self.digest,
                'worksheets': [{'name': name, 'data_rows': max(0, len(rows)-1),
                                'columns': len(rows[0]), 'preview': rows[:4]} for name, rows in self.tables.items()]}


def build_plan(payload: dict, targets: SheetTargets = SheetTargets()) -> SyncPlan:
    targets.validate()
    # Omit volatile generation timestamps: identical filtered reports have stable content.
    metadata = {k: v for k, v in payload['metadata'].items() if k != 'generated_at'}
    summary = [['metric', 'value']]
    for key, value in {**metadata, **payload['summary']}.items():
        summary.append([key, json.dumps(value, sort_keys=True) if isinstance(value, (dict, list, tuple)) else str(value)])
    tables = {targets.summary: summary,
              targets.orders: [ORDER_COLUMNS.copy()] + [[r[c] for c in ORDER_COLUMNS] for r in payload['orders']],
              targets.products: [TOP_COLUMNS.copy()] + [[r[c] for c in TOP_COLUMNS] for r in payload['top_products']]}
    canonical = json.dumps(tables, sort_keys=True, ensure_ascii=False).encode()
    if len(canonical) > MAX_BATCH_BYTES // 3:
        raise ValueError('Report is too large for one safe atomic Sheets update; narrow the filters.')
    return SyncPlan(tables, hashlib.sha256(canonical).hexdigest())


class SheetsClient:
    def __init__(self, token: Callable[[], str], client: httpx.Client,
                 sleep: Callable[[float], None] = time.sleep):
        self.token, self.client, self.sleep = token, client, sleep

    def _request(self, method: str, url: str, **kwargs) -> dict:
        for attempt in range(3):
            try:
                response = self.client.request(method, url, headers={'Authorization': 'Bearer ' + self.token()}, timeout=15, **kwargs)
            except httpx.TransportError as exc:
                if method != 'GET':
                    raise SheetsError('Write outcome unknown after a network failure. No success claimed; rerun the job to reconcile managed tabs.') from exc
                if attempt == 2:
                    raise SheetsError('Google Sheets read timed out or could not connect after 3 attempts.') from exc
                self.sleep(0.5 * 2 ** attempt)
                continue
            status = response.status_code
            if status in (401, 403):
                raise SheetsError('Google Sheets authentication or permission denied. Check API enablement and spreadsheet sharing.')
            if status == 404:
                raise SheetsError('Spreadsheet not found or not shared with this service account.')
            retryable = status == 429 or (method == 'GET' and status in (408, 500, 502, 503, 504))
            if retryable and attempt < 2:
                try:
                    wait = min(30.0, max(0.0, float(response.headers.get('Retry-After', '0'))))
                except ValueError:
                    wait = 0.0
                self.sleep(max(wait, 0.5 * 2 ** attempt) + random.uniform(0, 0.1))
                continue
            if status >= 400:
                if method != 'GET' and status >= 500:
                    raise SheetsError('Write outcome unknown after a Google server error. Rerun to reconcile; no success claimed.')
                raise SheetsError(f'Google Sheets request failed (HTTP {status}); no synchronization success claimed.')
            try:
                body = response.json()
                if not isinstance(body, dict):
                    raise ValueError
                return body
            except ValueError as exc:
                raise SheetsError('Invalid Google response; write outcome may be unknown. Rerun to reconcile.') from exc
        raise SheetsError('Google Sheets retry limit reached.')

    def verify(self, spreadsheet_id: str, plan: SyncPlan) -> dict:
        """Read every target cell back and compare with the expected snapshot.

        Evidence contains only validated synthetic report samples, never the
        spreadsheet ID, account identity, credentials, or unrelated worksheets.
        """
        if not re.fullmatch(r'[A-Za-z0-9_-]{10,200}', spreadsheet_id):
            raise ValueError('Invalid spreadsheet ID; use the ID, not the full URL.')
        params = [('ranges', "'" + name.replace("'", "''") + "'") for name in plan.tables]
        params.append(('valueRenderOption', 'UNFORMATTED_VALUE'))
        body = self._request('GET', f'{BASE_URL}/{spreadsheet_id}/values:batchGet', params=params)
        ranges = body.get('valueRanges')
        if not isinstance(ranges, list) or len(ranges) != len(plan.tables):
            raise SheetsError('Read-back did not return all target worksheets; verification failed.')
        evidence = []
        received_tables = []
        for (name, expected), received in zip(plan.tables.items(), ranges):
            if not isinstance(received, dict):
                raise SheetsError('Invalid read-back response; verification failed.')
            rows = received.get('values', [])
            expected_text = [[str(value) for value in row] for row in expected]
            if rows != expected_text:
                raise SheetsError('Remote worksheet content differs from the expected snapshot; verification failed.')
            received_tables.append(rows)
            evidence.append({'name': name, 'data_rows': len(rows) - 1,
                             'columns': len(rows[0]), 'headers': rows[0],
                             'sample_rows': rows[1:9], 'exact_match': True})
        orders = list(plan.tables.values())[1][1:]
        ids = [row[0] for row in orders]
        if len(ids) != len(set(ids)):
            raise SheetsError('Duplicate order IDs in report; verification failed.')
        summary = dict(received_tables[0][1:])
        order_columns = received_tables[1][0]
        order_records = [dict(zip(order_columns, row)) for row in received_tables[1][1:]]
        net_sales = sum((Decimal(row['net_sales']) for row in order_records), Decimal(0))
        paid_shipping = sum((Decimal(row['shipping_fee']) for row in order_records
                             if row['status'] in ('paid', 'shipped', 'completed')), Decimal(0))
        product_revenue = sum((Decimal(row[-1]) for row in received_tables[2][1:]), Decimal(0))
        if net_sales != Decimal(summary['net_sales']) or product_revenue + paid_shipping != net_sales:
            raise SheetsError('Read-back financial reconciliation failed.')
        return {'verified': True, 'digest': plan.digest, 'worksheets': evidence,
                'order_count': len(ids), 'unique_order_ids': len(set(ids)),
                'duplicate_orders': len(ids) - len(set(ids)),
                'financial_checks': {'net_sales_usd': str(net_sales.quantize(Decimal('0.01'))),
                                     'order_totals_match_summary': True,
                                     'product_revenue_plus_shipping_matches_sales': True}}

    def sync(self, spreadsheet_id: str, plan: SyncPlan, *, replace_managed: bool = False) -> dict:
        if not re.fullmatch(r'[A-Za-z0-9_-]{10,200}', spreadsheet_id):
            raise ValueError('Invalid spreadsheet ID; use the ID, not the full URL.')
        url = f'{BASE_URL}/{spreadsheet_id}'
        metadata = self._request('GET', url, params={'fields': 'sheets(properties(sheetId,title,gridProperties),developerMetadata)'})
        sheets = metadata.get('sheets')
        if not isinstance(sheets, list):
            raise SheetsError('Missing worksheet metadata; refusing writes.')
        existing = {}
        used = set()
        for sheet in sheets:
            try:
                properties = sheet['properties']
                if (not isinstance(properties['title'], str) or type(properties['sheetId']) is not int
                        or not isinstance(sheet.get('developerMetadata', []), list)):
                    raise TypeError
                if any(not isinstance(m, dict) or not isinstance(m.get('location', {}), dict)
                       for m in sheet.get('developerMetadata', [])):
                    raise TypeError
                existing[properties['title'].casefold()] = sheet
                used.add(properties['sheetId'])
            except (KeyError, TypeError, AttributeError) as exc:
                raise SheetsError('Invalid worksheet metadata; refusing writes.') from exc
        requests = []
        for title, rows in plan.tables.items():
            sheet = existing.get(title.casefold())
            if sheet is not None:
                props = sheet['properties']
                sid = props['sheetId']
                owned = any(m.get('metadataKey') == OWNER_KEY and m.get('metadataValue') == OWNER_VALUE
                            and m.get('location', {}).get('sheetId') == sid for m in sheet.get('developerMetadata', []))
                if not owned:
                    raise SheetsError('A target worksheet already exists without our ownership marker. Choose new dedicated names; no changes were written.')
                if not replace_managed:
                    raise SheetsError('Managed target already exists. Explicitly enable replace-managed-tabs to replace its entire report snapshot.')
                grid = props.get('gridProperties', {})
                if not isinstance(grid, dict) or any(type(grid.get(k, 1)) is not int
                                                    for k in ('rowCount', 'columnCount')):
                    raise SheetsError('Invalid grid metadata; refusing writes.')
                requests.append({'updateSheetProperties': {'properties': {'sheetId': sid, 'gridProperties': {
                    'rowCount': max(grid.get('rowCount', 1000), len(rows)),
                    'columnCount': max(grid.get('columnCount', 26), len(rows[0]))}}, 'fields': 'gridProperties.rowCount,gridProperties.columnCount'}})
            else:
                sid = random.SystemRandom().randrange(1, 2_000_000_000)
                while sid in used:
                    sid = random.SystemRandom().randrange(1, 2_000_000_000)
                used.add(sid)
                requests.extend([
                    {'addSheet': {'properties': {'sheetId': sid, 'title': title, 'gridProperties': {'rowCount': max(100, len(rows)), 'columnCount': max(10, len(rows[0]))}}}},
                    {'createDeveloperMetadata': {'developerMetadata': {'metadataKey': OWNER_KEY, 'metadataValue': OWNER_VALUE,
                        'location': {'sheetId': sid}, 'visibility': 'DOCUMENT'}}},
                ])
            # Explicit stringValue prevents formula execution and preserves decimal precision.
            cells = [{'values': [{'userEnteredValue': {'stringValue': str(value)}} for value in row]} for row in rows]
            # Full-sheet range clears stale values after shorter snapshots; unrelated tabs untouched.
            requests.append({'updateCells': {'range': {'sheetId': sid}, 'rows': cells, 'fields': 'userEnteredValue'}})
        body = {'requests': requests, 'includeSpreadsheetInResponse': False}
        if len(json.dumps(body).encode()) > MAX_BATCH_BYTES:
            raise ValueError('Sheets request exceeds safe size limit; narrow the filters.')
        response = self._request('POST', url + ':batchUpdate', json=body)
        replies = response.get('replies')
        if (response.get('spreadsheetId') != spreadsheet_id or not isinstance(replies, list)
                or len(replies) != len(requests)):
            raise SheetsError('Google did not confirm the full batch. Outcome unknown; rerun to reconcile.')
        return {'status': 'synchronized', 'digest': plan.digest, 'worksheets': len(plan.tables),
                'orders': max(0, len(list(plan.tables.values())[1])-1), 'atomic': True,
                'writes_performed': True, 'remote_writes_performed': True}
