"""Read-only full snapshot verification. Configuration comes only from environment.

Run from project root: .venv/bin/python scripts/verify_sheets.py
Optional --evidence writes only verified synthetic samples and sanitized counts.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.automation import make_report
from src.sheets import SheetTargets, SheetsClient, SheetsError, build_plan
from src.sheets_auth import AccessToken, CredentialError, load_credentials


def main() -> int:
    parser = argparse.ArgumentParser(description='Read-only verification of the offline demo snapshot in Google Sheets.')
    parser.add_argument('--evidence', type=Path, help='Save sanitized verification evidence; no spreadsheet ID or credentials.')
    args = parser.parse_args()
    sid = os.environ.get('GOOGLE_SHEETS_SPREADSHEET_ID')
    if not sid:
        print('Spreadsheet ID is not configured.', file=sys.stderr)
        return 2
    try:
        targets = SheetTargets(os.environ.get('GOOGLE_SHEETS_SUMMARY_SHEET', 'CommerceFlow_Summary'),
                               os.environ.get('GOOGLE_SHEETS_ORDERS_SHEET', 'CommerceFlow_Orders'),
                               os.environ.get('GOOGLE_SHEETS_PRODUCTS_SHEET', 'CommerceFlow_TopProducts'))
        payload = make_report('offline')
        plan = build_plan(payload, targets)
        with httpx.Client(follow_redirects=False) as http:
            evidence = SheetsClient(AccessToken(load_credentials()), http).verify(sid, plan)
        evidence.update(verified_at=datetime.now(timezone.utc).isoformat(),
                        disclosure='DEMO / SYNTHETIC DATA',
                        source='Actual Google Sheets API read-back; all target cells compared with expected offline report.',
                        summary=payload['summary'])
        if args.evidence:
            args.evidence.parent.mkdir(parents=True, exist_ok=True)
            args.evidence.write_text(json.dumps(evidence, indent=2, ensure_ascii=False))
        print(json.dumps({k: v for k, v in evidence.items() if k != 'worksheets'}, indent=2))
        print(json.dumps({'worksheets': [{k: w[k] for k in ('name', 'data_rows', 'columns', 'exact_match')} for w in evidence['worksheets']]}, indent=2))
        return 0
    except (CredentialError, SheetsError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 4


if __name__ == '__main__':
    raise SystemExit(main())
