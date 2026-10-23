# Reproducible portfolio demonstration

All order/customer/revenue data is fictional. Live product metadata comes from
DummyJSON; the bundled catalog is explicitly authored fictional data.

## Dashboard walkthrough (no Google credentials required)

1. Start `.venv/bin/python -m streamlit run app.py --server.port 8502` from the project root.
2. Open `http://localhost:8502`. Keep the offline source for the baseline figures.
3. Overview: select July–September 2026 and all statuses. Confirm 240 selected orders,
   186 recognized orders, USD 43,204.59 recognized sales, AOV USD 232.28, and 1,142 units.
4. Orders Explorer: search `DEMO-00001`, inspect the normalized order and its line items.
   Clear the search afterward. Change date/status filters and observe consistent changes.
5. Sales Analytics: inspect daily trend, top products, statuses, and reconciliation.
6. Report Export: download CSV, JSON, Excel. Excel has Summary, Orders, OrderItems,
   TopProducts sheets. All monetary exports use exact USD decimal strings.
7. Google Sheets Integration: inspect the current selection's dry-run. This public
   page never writes to Sheets and does not claim authentication success.
8. API Connection / Data Source: click Fetch products from DummyJSON. Confirm the
   live retrieval status/count/timestamp and normalized products. Catalog switching
   regenerates synthetic orders, so KPIs can change. Return to bundled offline
   products to reproduce the baseline.

## Independent CLI walkthrough

No Streamlit process is needed:

```bash
.venv/bin/python -m src.automation --dry-run
.venv/bin/python -m src.automation --export-dir artifacts/demo-exports --search DEMO-00001
```

For authorized Google Sheets demonstration, configure the environment securely as
explained in PHASE3.md; no destination identifiers or credentials are in this repo.
Use a dedicated test spreadsheet and do not manually create the managed target tabs.

```bash
.venv/bin/python -m src.automation --sync
.venv/bin/python scripts/verify_sheets.py --evidence artifacts/first-sync-verification.json
.venv/bin/python -m src.automation --sync --replace-managed-tabs
.venv/bin/python scripts/verify_sheets.py --evidence artifacts/repeat-sync-verification.json
```

If managed tabs already exist, the first command requires the explicit
`--replace-managed-tabs` option too. Existing unmanaged same-name tabs are refused;
choose new names rather than overwriting them. Compare both verification digests,
row counts, and unique order counts; expected baseline is 240 unique orders on each
run and zero duplicates. Read-back verification checks every target cell and
independently reconciles order sales, summary sales, and product sales plus shipping.

## Screenshots

```bash
.venv/bin/python scripts/capture_portfolio.py
```

Requires a local app on port 8502, Google Chrome, Playwright, and the checked-in,
sanitized `docs/portfolio/sheets-verification.json` containing actual read-back and
repeat-sync evidence. The script captures the actual app and performs a fresh
public product API request. API failure stops capture rather than fabricating a
successful image. The Google Sheets image renders the dated, verified read-back
samples as an explicitly labelled evidence page; it is not a Google account or
Sheets-editor screenshot. Capturing it does not perform new Google authentication.

Checked-in evidence is a historical verification snapshot, not a live connection
indicator. Regenerate live verification only on a trusted machine with your own
explicit destination configuration. Keep the prior verification snapshot when
comparing a rerun. `docs/portfolio/capture-report.json` records capture provenance.
