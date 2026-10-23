# Phase 3: Google Sheets and independent automation

Real Google Sheets writes were completed on an authorized test spreadsheet on
2026-10-23. Two synchronizations and full API read-back checks verified 240 unique
synthetic orders without duplicates. Unit tests still use mocked Google responses.
No scheduler is installed. See ../VALIDATION.md and portfolio/sheets-verification.json
for dated, sanitized evidence; no credentials or destination identifiers are stored.

## Authorize Google Sheets manually

1. Create/select a Google Cloud project and enable **Google Sheets API**.
2. Create a dedicated service account and, if organizational policy permits,
   create a JSON service-account key. No domain-wide delegation, OAuth browser
   consent flow, Drive API, or broad project Editor role is required for this app.
3. Create a spreadsheet yourself and share **only that spreadsheet** with the
   service account's `client_email` as an Editor. Organization sharing policies
   may require an administrator. This app does not create Drive files.
4. Store the JSON key **outside this repository**, in an access-controlled folder.
   On Linux use directory mode `700` and key file mode `600`, owned by the job user.
   The loader refuses group/world-accessible files on POSIX systems.
5. Set the environment variables below locally. Never send the key in chat,
   commit it, print it in logs, or pass JSON as a CLI argument.

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/absolute/protected/path/service-account.json
export GOOGLE_SHEETS_SPREADSHEET_ID=YOUR_SPREADSHEET_ID
```

The spreadsheet ID is the portion between `/d/` and `/edit` in its browser URL.
The app validates it as an ID, not a URL. Use `GOOGLE_SERVICE_ACCOUNT_JSON` instead
of the file variable when a trusted secret manager injects the JSON directly into
the job environment. Configure **exactly one** credential source. The loader only
accepts a service-account credential using Google's official OAuth token endpoint.
Tokens are obtained using official `google-auth` with only the Sheets scope.

`.env.example` is a template, not automatically loaded. Keep an actual environment
file outside the repository and protect it with `chmod 600`. Shell-source only a
file you trust; sourcing executes shell syntax. Rotate/revoke keys when necessary.
Do not attach production Sheets credentials to an unauthenticated public demo.

References: [Google service-account credentials](https://developers.google.com/workspace/guides/create-credentials#service-account),
[google-auth](https://google-auth.readthedocs.io/en/latest/reference/google.oauth2.service_account.html).

## Standalone commands

```bash
cd /home/michael/ai-workspace/ecommerce-api-automation
.venv/bin/python -m src.automation --help

# Default offline products; no Google calls, credential parsing, or local writes.
.venv/bin/python -m src.automation --dry-run

# Same rules and filters as the dashboard; repeat --status as needed.
.venv/bin/python -m src.automation --dry-run \
  --start 2026-07-01 --end 2026-07-31 --status completed --status shipped

# A single normalized order, with three local export formats in a new run folder.
.venv/bin/python -m src.automation --export-dir artifacts/automation --search DEMO-00001

# First synchronization: requires real credentials and spreadsheet sharing.
# Choose names that DO NOT already exist. Do not create these tabs manually.
.venv/bin/python -m src.automation --sync

# Explicit consent to replace managed target snapshots on subsequent runs.
.venv/bin/python -m src.automation --sync --replace-managed-tabs

# Custom destination names; also configurable through environment variables.
.venv/bin/python -m src.automation --sync \
  --summary-sheet Demo_Summary --orders-sheet Demo_Orders --products-sheet Demo_Products

# Live product API (orders/revenue remain synthetic; API failure is explicit).
.venv/bin/python -m src.automation --source api --dry-run
```

Running without `--sync` or `--export-dir` defaults to dry-run. `--dry-run` overrides
`--sync` and never needs a spreadsheet ID or credentials; it cannot be combined
with `--export-dir`. With `--source api`, it still explicitly fetches the public
product API, but never calls Google. Preview includes local sample rows, row counts,
summary metrics, and a stable content hash. **It does not inspect remote data or
validate permissions**, so it cannot predict tab conflicts or promise sync success.
No Streamlit module is imported or server required by this CLI.

Date filters and statuses behave like the dashboard. CLI omission of `--status`
means all statuses; repeat the option to choose a subset. Use `--search` to narrow
order IDs. All revenue and customer/order records remain DEMO / SYNTHETIC DATA.

Exit codes: `0` completed action/dry-run, `2` invalid options/configuration/report,
`3` credential/authentication-token failure, `4` API/Sheets failure (including
uncertain write result), `5` local export I/O failure. Google permission errors
returned by Sheets use `4`. Help uses `0`. Errors are sanitized JSON on stderr;
report previews/results are JSON on stdout. Never enable HTTP debug logging in a
credentialed job. If both sync and local export are selected, sync runs first;
a later disk failure cannot roll back the already committed remote batch.

## Explicit synchronization strategy

This is a **replace-current-snapshot** strategy, not an append-only ledger or
order-by-order merge with human-maintained data.

- Three dedicated tabs contain summary, filtered orders, and top product sales.
  Names default to `CommerceFlow_Summary`, `CommerceFlow_Orders`, and
  `CommerceFlow_TopProducts`. Override with CLI options or
  `GOOGLE_SHEETS_SUMMARY_SHEET`, `GOOGLE_SHEETS_ORDERS_SHEET`, and
  `GOOGLE_SHEETS_PRODUCTS_SHEET`.
- The first successful batch creates missing tabs and tags them with sheet-scoped
  developer metadata: `commerceflow_owner=commerceflow_snapshot_v1`.
- **Any existing target without this marker is refused, even when empty.** Choose
  new names; this app never adopts or deletes an existing unowned worksheet.
- Replacing a managed tab requires `--replace-managed-tabs`. This authorizes
  replacing **all cell values and formulas in those three tabs**, including manual
  edits, using the current filtered report. Keep manual notes in other tabs.
- Changing filters replaces the snapshot with that filtered subset. Orders outside
  the new filter disappear from these report tabs; they are not deleted from any
  source system. Empty selections replace reports with headers only.
- One Sheets `spreadsheets.batchUpdate` request combines creates, ownership markers,
  necessary grid expansion, and all three full-sheet `updateCells` requests.
  Google applies the batch atomically: a rejected subrequest leaves the batch
  unapplied. There is no separate clear-then-write step.
- `userEnteredValue` is the only cell field replaced. The full-sheet range clears
  stale values after shorter reports. Other worksheets are untouched. Existing
  formatting is retained; this is not intended to manage charts or manual merges.
- All values use explicit `stringValue`, preventing formulas from executing and
  preserving decimal strings/IDs. Sheets monetary values are text USD, matching
  JSON/Excel precision conventions.
- Repeating a job replaces the same rows instead of appending duplicate orders.
  Volatile generation timestamps are excluded from the report hash and Sheets
  summary, so identical reports have stable content. The hash is diagnostic, not
  a distributed lock or remote verification. Identical data may still be rewritten.
- Use **one writer per destination tab set**. Cron `flock` and Actions concurrency
  examples serialize jobs in their own environments. They do not coordinate with
  each other, human edits, or other hosts. Separate those destinations or schedule
  a single writer. Developer metadata is an ownership convention, not an access
  security boundary; do not edit or forge it.

Official behavior: [batch updates](https://developers.google.com/workspace/sheets/api/guides/batchupdate),
[updateCells ranges](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets/request#UpdateCellsRequest).

## Errors and limits

Reads retry transient transport failures/408/429/5xx up to three attempts. Writes
retry explicit 429 rate-limit rejections only; exponential backoff includes jitter
and bounded numeric `Retry-After`. Google reads/writes use a 15-second HTTP timeout;
token refresh uses a 10-second timeout. Authentication and permissions errors fail
clearly without exposing response bodies, keys, or tokens.

**A network failure or server error after sending a write can have an unknown
outcome.** The CLI returns failure, never success; rerun with
`--replace-managed-tabs` to read fresh metadata and reconcile to the same snapshot.
No blind retry of an ambiguous creation request is performed. If a batch was
rejected, the three reports remain unchanged. A successful sync is reported only
when Google confirms the expected spreadsheet and every batch reply.

Payloads above the safe single-batch cap (1.9 MB encoded batch) are rejected before
writes; narrow the order/date filters. A conservative local plan-size guard also
prevents expensive oversized batches. No chunked partial updates are performed.
Sheets has usage quotas; this application does not require paid Google services.
GitHub Actions availability/minutes depend on your account; Linux cron is an
independent local option. See [Google Sheets limits](https://developers.google.com/workspace/sheets/api/limits).

## Streamlit and public hosting

The new **Google Sheets Integration** page shows `Not configured` or
`Configured (not authenticated)` without printing secrets or paths. It previews
the **current dashboard selection** using the same report planner. It never claims
that configuration means permission verification or a successful synchronization.

For an unauthenticated public demo, writes are intentionally available only in the
trusted standalone CLI. There is no credential entry, upload, remote write button,
or secret-bearing cache. Existing dashboard pages, offline mode, and downloads
remain available without credentials. The legacy Integrations (Coming Soon) route
is retained as a scheduling roadmap and does not falsely claim that jobs run.

## Schedule independently of Streamlit

### Linux cron

1. Install dependencies in the project's virtual environment.
2. Create an external `700` configuration directory, a `600` service-account key,
   and a `600` `job.env` based on `.env.example`. Set the credential path, spreadsheet
   ID, and dedicated sheet names. Do not put secrets in the crontab.
3. Run `--dry-run`, then manually authorize the first `--sync` and inspect Sheets.
4. Review and adapt `examples/commerceflow.cron`; add it with your own `crontab -e`.
   Paths, user, permissions, host timezone, log rotation, and retention are your
   responsibility. `flock` prevents overlapping jobs on the same host.
5. Check job exit codes/logs; stop the schedule before changing destinations.

The sample runs daily at 07:00 in the host's timezone. Nothing has been installed
into your crontab by this implementation.

### GitHub Actions

`examples/google-sheets-sync.yml` is an **inactive example**, not a workflow in
`.github/workflows/`. After separately approving publication:

1. Create environment `sheets-production` with repository/environment access rules.
2. Add secrets `GOOGLE_SERVICE_ACCOUNT_JSON` and
   `GOOGLE_SHEETS_SPREADSHEET_ID`. The JSON is an environment secret; no file needs
   to be committed. Do not echo it or upload it as an artifact.
3. Copy the reviewed example into `.github/workflows/`, inspect action versions,
   and pin action commit SHAs if required by your repository policy.
4. Run `workflow_dispatch` first and inspect the dedicated sheet snapshots.
5. Enable/review its UTC schedule (23:00 UTC = 07:00 Asia/Taipei). Scheduled Actions
   can be delayed and require the workflow on the default branch; they are not a
   real-time scheduling guarantee. Concurrency prevents overlapping runs of this
   workflow. Do not also target the same sheets from cron.

Do not inject credentials into untrusted pull-request jobs. Real Sheets writes were explicitly authorized and verified. GitHub source publication was authorized separately. No application deployment,
secret creation, workflow activation, or cron installation has been performed. [GitHub scheduling documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).


## Read-back verification

After a successful CLI sync, run `scripts/verify_sheets.py` with the same environment
to read every managed worksheet cell and compare it to the deterministic offline
report. It also checks unique order IDs and monetary reconciliation.

```bash
.venv/bin/python scripts/verify_sheets.py --evidence artifacts/readback.json
```

This command is read-only. It stores only verified synthetic samples, counts,
metrics, and timestamps when an evidence output is explicitly requested. It never
stores credential paths, account identity, tokens, or a spreadsheet ID. It verifies
the full unfiltered offline baseline; use the dashboard for arbitrary filter previews.
