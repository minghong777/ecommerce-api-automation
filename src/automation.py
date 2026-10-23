"""Standalone CLI: python -m src.automation --help. Does not import Streamlit."""
import argparse
from datetime import date
import json
import os
from pathlib import Path
import sys
from typing import Sequence
import httpx
from .api_client import APIError, fetch_products
from .config import STATUSES
from .demo_data import generate_dataset, offline_products
from .metrics import Filters, filter_dataset
from .reports import export_csv, export_excel, export_json, report
from .sheets import SheetTargets, SheetsClient, SheetsError, build_plan
from .sheets_auth import AccessToken, CredentialError, load_credentials


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description='CommerceFlow synthetic sales automation. No Streamlit server required.')
    result.add_argument('--source', choices=('offline', 'api'), default='offline', help='Product catalog; API errors fail explicitly (no silent fallback).')
    result.add_argument('--start', type=date.fromisoformat, help='Inclusive UTC start date (YYYY-MM-DD); default dataset start.')
    result.add_argument('--end', type=date.fromisoformat, help='Inclusive UTC end date; default dataset end.')
    result.add_argument('--status', action='append', choices=STATUSES, help='Repeat to select statuses; omitted means all.')
    result.add_argument('--search', default='', help='Case-insensitive order-ID substring.')
    result.add_argument('--dry-run', action='store_true', help='Preview local snapshot; no Google requests, credentials, or output files. Default if no action selected.')
    result.add_argument('--sync', action='store_true', help='Write dedicated tabs through the official Google Sheets API.')
    result.add_argument('--replace-managed-tabs', action='store_true', help='Explicitly allow replacing ALL values in app-owned target tabs; never adopt unmanaged tabs.')
    result.add_argument('--spreadsheet-id', default=os.environ.get('GOOGLE_SHEETS_SPREADSHEET_ID'), help='Spreadsheet ID; defaults to GOOGLE_SHEETS_SPREADSHEET_ID.')
    result.add_argument('--summary-sheet', default=os.environ.get('GOOGLE_SHEETS_SUMMARY_SHEET', 'CommerceFlow_Summary'))
    result.add_argument('--orders-sheet', default=os.environ.get('GOOGLE_SHEETS_ORDERS_SHEET', 'CommerceFlow_Orders'))
    result.add_argument('--products-sheet', default=os.environ.get('GOOGLE_SHEETS_PRODUCTS_SHEET', 'CommerceFlow_TopProducts'))
    result.add_argument('--export-dir', type=Path, help='Explicitly save CSV, JSON, Excel locally. Uses a new run directory; never overwrites files.')
    return result


def make_report(source: str, start: date | None = None, end: date | None = None,
                statuses: tuple[str, ...] = STATUSES, search: str = '') -> dict:
    if source == 'api':
        products = fetch_products().products
        provenance = 'DummyJSON public product API + synthetic commerce'
    else:
        products = offline_products()
        provenance = 'Bundled fictional products · offline'
    data = generate_dataset(products)
    filters = Filters(start or min(o.order_date.date() for o in data.orders),
                      end or max(o.order_date.date() for o in data.orders), statuses, search)
    return report(filter_dataset(data, filters), filters, provenance)


def save_exports(payload: dict, destination: Path) -> str:
    import tempfile
    destination.mkdir(parents=True, exist_ok=True)
    files = {'orders.csv': export_csv(payload), 'report.json': export_json(payload), 'report.xlsx': export_excel(payload)}
    folder = Path(tempfile.mkdtemp(prefix='commerceflow-', dir=destination))
    try:
        for name, content in files.items():
            path = folder / name
            with path.open('xb') as stream:
                stream.write(content)
            path.chmod(0o600)
    except OSError:
        for path in folder.iterdir():
            path.unlink()
        folder.rmdir()
        raise
    return str(folder)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser()
    args = arguments.parse_args(argv)
    if args.dry_run and args.export_dir:
        arguments.error('--dry-run cannot write local exports; omit --export-dir.')
    if args.sync and not args.dry_run and not args.spreadsheet_id:
        arguments.error('--sync requires a spreadsheet ID or GOOGLE_SHEETS_SPREADSHEET_ID.')
    if args.start and args.end and args.start > args.end:
        arguments.error('--start must be on or before --end.')
    try:
        payload = make_report(args.source, args.start, args.end,
                              tuple(args.status) if args.status else STATUSES, args.search)
        plan = build_plan(payload, SheetTargets(args.summary_sheet, args.orders_sheet, args.products_sheet))
        result = plan.preview()
        result['disclosure'] = 'DEMO / SYNTHETIC DATA'
        result['summary'] = payload['summary']
        if args.sync and not args.dry_run:
            # Validate credentials before exporting files or calling Google.
            credentials = load_credentials()
            with httpx.Client(follow_redirects=False) as client:
                result = SheetsClient(AccessToken(credentials), client).sync(
                    args.spreadsheet_id, plan, replace_managed=args.replace_managed_tabs)
        if args.export_dir and not args.dry_run:
            result['export_directory'] = save_exports(payload, args.export_dir)
            result['writes_performed'] = True
            result['local_exports_written'] = True
            if not args.sync:
                result['mode'] = 'local-export'
                result['remote_writes_performed'] = False
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (CredentialError, SheetsError, APIError) as exc:
        print(json.dumps({'status': 'failed', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 3 if isinstance(exc, CredentialError) else 4
    except ValueError as exc:
        print(json.dumps({'status': 'failed', 'error': str(exc)}), file=sys.stderr)
        return 2
    except OSError:
        print(json.dumps({'status': 'failed', 'error': 'Local export failed; check disk space and output permissions. If a remote sync was requested it may already have completed.'}), file=sys.stderr)
        return 5


if __name__ == '__main__':
    raise SystemExit(main())
