# Verification record

## How to read this record

This is a chronological audit log. Results below describe the code and external
services **at the time of each check**, not current connectivity. The Phase 1/2
and initial mocked Phase 3 sections are historical and superseded by the authorized
live verification and publication sections. The final-review section records local preparation at that time. A subsequent
authorized publication section records the 2026-10-25 update; the app remains undeployed.

- Google Sheets evidence: historical authorized test on 2026-10-23; not live status.
- Existing public GitHub repository: https://github.com/minghong777/ecommerce-api-automation
- Streamlit public deployment: not performed; no scheduler enabled.
- The original unrelated worksheet was retained during the historical sync.

## Historical Phase 1/2 verification

Verified locally on 2026-10-22 using Python 3.12.15.

## Automated checks

Command:

```bash
.venv/bin/python -m pytest -q
```

Final result: **52 passed in 1.26s**.

Includes HTTP mock failures/retries/pagination/size limits, deterministic offline data,
foreign keys and money validation, purchase-price preservation, cancellation/refund
rules, largest-remainder discount allocation, UTC filters, AOV rounding,
CSV/JSON/Excel contents, empty exports, formula injection defenses, and all six
Streamlit workspaces through AppTest.

## Live API

Command:

```bash
.venv/bin/python -c "from src.api_client import fetch_products; r=fetch_products(); print(len(r.products), r.total, r.requests, r.fetched_at.isoformat())"
```

Observed: **194 products, 194 total, 4 HTTP requests**, fetched at
`2026-10-22T11:23:58.456023+00:00`. This confirms actual paginated public access
from this environment, not future availability of the external service.

## Real browser

App server:

```bash
.venv/bin/python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8502 --server.headless true
```

Command:

```bash
.venv/bin/python scripts/browser_check.py
```

Final result: **passed**. Chromium checked Overview and all five remaining pages,
downloaded CSV/JSON/Excel, verified the full JSON had 240 orders, searched for one
order and verified a new JSON export had exactly one order. A separate 390 × 844
mobile browser rendered without Streamlit exceptions or page-level horizontal
overflow. Desktop and mobile screenshots are in ignored `artifacts/`.

A download cancellation during verification was traced to Streamlit rerunning the
page on download clicks; download buttons now use `on_click='ignore'`. The full
pytest suite and browser verification passed after that change. A mobile header
spacing issue and the AppTest entrypoint path were also corrected.

## Reproducible offline baseline

- Orders: 240; recognized paid/shipped/completed: 186.
- Recognized sales: USD 43,204.59.
- AOV: USD 232.28; recognized units: 1,142.
- All values are calculated synthetic results, not real sales.

No credentials are required. No deployment or repository push was performed.
Known scope limits: no partial refunds/tax/FX, no persistent transactions, no Sheets
connection, no scheduled CLI yet. Requirements use version ranges; exact installed
packages for this verification are in `requirements-lock.txt`.

---

## Historical initial Phase 3 verification (mocked Google responses)

The earlier record above is retained as Phase 1/2 history. Its statements that no
Sheets client or scheduled CLI exists are superseded by this section.

Verified locally on 2026-10-22, Python 3.12.15.

```bash
.venv/bin/python -m pytest -q
```

Final result: **88 passed in 2.28s** (all original 52 tests plus 36 Phase 3 cases).
New coverage includes protected/missing/malformed credentials, official token
refresh timeout, sanitized auth errors, HTTP 401/403/404/429/5xx and transport
failures, bounded retries, refusal of unmanaged tabs, explicit managed replacement,
atomic batch construction, stale-row clearing, repeat-run idempotency, recovery
after a simulated committed write with lost response, formula-safe text cells,
malformed metadata, missing batch confirmation, CLI sync wiring, local exports,
filter consistency, credential-free dry-run, and the integration UI.

Google responses, authentication, and write outcomes are **mocked**. No real
service-account credential was supplied, no actual Google spreadsheet was read or
written, and no success against a real spreadsheet is claimed.

```bash
.venv/bin/python scripts/browser_check.py
```

Result: **passed**. All seven workspaces (including Google Sheets Integration and
the preserved legacy integration route) rendered. CSV, JSON, Excel downloads passed;
the shared order filter produced exactly one exported order. The 390-pixel mobile
check passed. The public integration page works with no credentials and exposes no
write action.

Additional executed CLI checks:

```bash
.venv/bin/python -m src.automation --help
.venv/bin/python -m src.automation --dry-run --start 2026-07-01 --end 2026-07-31 --status completed
.venv/bin/python -m src.automation --export-dir artifacts/phase3-cli --search DEMO-00001
```

Help, preview, and three-format local export succeeded. A direct CLI invocation
with an empty credential environment and `--sync` returned exit code **3**, a
sanitized failure, and no success output. A subprocess test confirms the CLI does
not import Streamlit. No server is required for CLI jobs.

No Google credentials, token values, or API keys are present in project source.
Credential paths/JSON are configured externally, never through chat or CLI args.
Credential filename patterns and local environment files are ignored by Git.

At that historical stage, remaining manual authorization was: enable Sheets API, create a dedicated service
account/key, protect it outside the repository, share a dedicated spreadsheet,
review dry-run, perform the first actual sync and a repeat run, then optionally
install exactly one reviewed scheduler. See docs/PHASE3.md.

Cron and GitHub Actions examples are inactive files in examples/. No crontab entry,
active workflow, deployment, repository push, or external write was created.

---

## Authorized live delivery verification — 2026-10-23

This section supersedes the earlier historical statements about the absence of
real Sheets writes. A user-provided test spreadsheet was explicitly authorized.
Its ID and the service-account credentials are deliberately excluded from this
record, source code, screenshots, and portfolio evidence.

### Environment and authorization

Python 3.12.15; virtual environment and required dependencies available. The
service-account JSON was validated outside the repository. Key file mode: 600;
parent directory mode: 700; current-user ownership checked. Credential contents,
account identity, tokens, and private keys were not printed. Each live command was
launched with explicit subprocess environment configuration rather than relying
on variables exported in another shell. Read-only Sheets API returned HTTP 200.
Initially only one unrelated worksheet existed; no target-name collision occurred.

### Real synchronization and read-back

Executed with securely supplied environment variables:

```bash
.venv/bin/python -m src.automation --dry-run
.venv/bin/python -m src.automation --sync
.venv/bin/python scripts/verify_sheets.py --evidence artifacts/first-sync-verification.json
.venv/bin/python -m src.automation --sync --replace-managed-tabs
.venv/bin/python scripts/verify_sheets.py --evidence docs/portfolio/sheets-verification.json
```

Both writes returned confirmed successful batch responses. Both read-backs matched
**all cells**, including headers, purchase dates, statuses, counts, and money values.
The second snapshot had the same digest and row contents as the first.

| Managed worksheet | Data rows (header excluded) | Columns |
|---|---:|---:|
| CommerceFlow_Summary | 19 | 2 |
| CommerceFlow_Orders | 240 | 10 |
| CommerceFlow_TopProducts | 12 | 5 |

There were 240 distinct order IDs before and after the rerun, zero duplicates, and
no accumulation. Post-sync metadata confirmed all three ownership markers and the
original unrelated worksheet still present with its original sheet ID (four total
tabs). No write targeted the unrelated worksheet.

Independent Decimal reconciliation of actual remote rows confirmed:

- Recognized synthetic sales: USD 43,204.59 (186 recognized orders).
- Paid merchandise USD 45,357.77 − discounts USD 2,482.63 + shipping USD 329.45
  = recognized sales USD 43,204.59.
- Product-level net revenue plus recognized shipping equals recognized sales.
- Units sold: 1,142; AOV: USD 232.28.
- All customers, orders, and revenue remain fictional.

Read-back verification is now reusable in SheetsClient.verify and the standalone
scripts/verify_sheets.py utility. Evidence contains only validated fictional samples,
counts, financial checks, and timestamps; it is a dated snapshot, not a permanent
live-status claim. Full equality is checked before any samples are saved.

### Final automated and browser checks

```bash
.venv/bin/python -m pytest -q
```

**93 passed in 2.30s**, including all original tests plus exact read-back, unexpected
or duplicate remote rows, and financial-reconciliation failure coverage.

```bash
.venv/bin/python scripts/browser_check.py
```

**Passed:** all seven workspaces, actual CSV/JSON/Excel downloads, filtered export
with one order, and a 390-pixel mobile browser. The Streamlit server is local only
on 127.0.0.1:8502 and was started without Google credentials.

```bash
.venv/bin/python scripts/capture_portfolio.py
```

**Passed:** six portfolio images captured. The API source screenshot used a fresh
successful DummyJSON fetch of 194 products across four HTTP attempts. Google Sheets
verification screenshot is an explicitly labelled rendering of actual read-back
evidence, not the Google Sheets editor or a fake connectivity mockup.

### Delivery and publication boundary

English README, demo walkthrough, publication preparation, and Upwork copy are
prepared. Upwork description: 536 characters; five skills. Portfolio assets include
six images, sanitized Sheets evidence, and captions. Existing source files contain
no credential JSON, private keys, access tokens, or target spreadsheet ID. Ignore
rules exclude credentials, secret configurations, runtime exports, and artifacts.
Source and portfolio packages exclude the virtual environment, runtime files, and
credentials. At this pre-publication stage, no Git commit, push, public deployment,
scheduler activation, or cron installation had been performed. The GitHub publication
section below supersedes the source-publication status. No external permission action remains necessary
for this verified test integration; publication and scheduling await owner approval.

---

## GitHub publication checks — 2026-10-23

The owner explicitly authorized GitHub source publication after reviewing the live
Sheets results. The project is isolated in its own Git repository; other workspace
projects are excluded. Commit identity uses a GitHub noreply address.

Pre-publication test command: `.venv/bin/python -m pytest -q`.
Result: **93 passed in 2.77s**.

All publication candidate files were scanned for the real service-account key,
key identifier, account identity, access-token/private-key markers, and destination
spreadsheet identifier. No matches were found. Git ignore checks passed for
credentials, private environment files, Streamlit secrets, virtual environments,
exports, and runtime artifacts. Six screenshots contain synthetic data only.
No active GitHub workflow, cloud application deployment, or scheduler is included.

Repository: https://github.com/minghong777/ecommerce-api-automation

---

## Final public-portfolio review — 2026-10-23 (local, not pushed)

This is the latest local review. The existing public GitHub main branch remains at
its previously published commit; none of this review's changes have been committed
or pushed. No app deployment, credentialed Google call, Sheets write, or scheduler
activation was performed during this review.

### Actual tests and clean-environment checks

- Baseline: `.venv/bin/python -m pytest -q` → **93 passed in 2.65s**.
- After fixes and public-boundary tests: `.venv/bin/python -m pytest -q` →
  **96 passed in 3.58s**.
- `uv pip check --python .venv/bin/python` → all installed packages compatible.
- Installed root `requirements.txt` into a newly created Python 3.12 virtualenv
  under ignored `artifacts/release-review-venv/`; dependency installation succeeded.
- Copied the release candidate to a different source directory, then ran its tests
  **from that directory** using the fresh virtualenv: **96 passed in 5.74s**.
  This invocation used the relocated source and fixtures, not the original cwd.
- Ran `python -m src.automation --dry-run` from the relocated source; exit 0, no
  remote checks or writes, 240 synthetic orders and the documented baseline KPIs.
- Started the relocated `app.py` from `/tmp` on a loopback-only test server without
  any Google credential variables or web secrets. It rendered successfully.
- `.venv/bin/python scripts/browser_check.py --url http://127.0.0.1:8503` → **passed**.
  All seven desktop and seven 390-pixel mobile pages rendered without exceptions
  or page-level horizontal overflow. CSV/JSON/Excel downloads succeeded; order-ID
  filtering produced exactly one order in the actual JSON download.

The three additional pytest cases assert that the web entrypoint refuses either
credential environment source without loading it, and all normal public pages
never call the Google credential loader, token provider, or Sheets synchronization.
Existing local CLI tests remain passing. Mock authentication/HTTP tests do not
access the real service-account key or Google Sheets.

### Findings and minimal corrections

1. The original Streamlit lower bound 1.45 permitted a version whose dataframe API
   cannot accept the `width='stretch'` argument used by this app. Requirements now
   require the successfully tested 1.66.1 or later within major version 1.
2. Old validation sections were labelled as current despite being superseded by
   the authorized live verification. The audit log now clearly separates history,
   real verification, prior publication, and this unpushed local review.
3. The public web entrypoint now stops when service-account credential environment
   variables are attached. Private synchronization is retained in the standalone
   CLI; Community Cloud must use no Google Secrets or spreadsheet destination.
4. The Sheets evidence image now explicitly says **historical verified read-back**
   and **not a live connection**. Its original API evidence JSON is unchanged.
5. The browser script now accepts a configurable URL and checks every mobile page,
   rather than only the mobile overview. A fragile first-button selector used
   during diagnostic exploration was replaced by the actual sidebar controls.
6. The Sales Analytics image was reframed by normal page scrolling so all seven
   financial-reconciliation rows are visible. No image data or KPIs were fabricated.

All six portfolio images were visually reviewed against their app/report sources.
The other five original app/evidence data sets remain reproducible from the
bundled catalog or their dated API capture; a static screenshot is not a live API
availability claim. Upwork copy is now 512 characters with five skills, a complete
image order, captions, a source link, and truthful live-demo placement guidance.

### Security and publication boundary

Scanned current release files and every blob in Git history for real credential
values, key/token markers, account identity, and private spreadsheet identifiers;
no matches found. Credential JSON is outside the repository and is not tracked.
Git ignore checks passed for `.env`, Streamlit secrets, service-account JSON,
virtualenvs, exports, and artifacts. No public Sheets URL, ID, token, or key is
included in the screenshots, README, historical evidence, or release packages.
Application/runtime modules contain no hard-coded `/home/` or `/tmp/` paths.
No active `.github/workflows` directory or web secrets file exists.

Prepared deployment values are documented in docs/DEPLOYMENT.md: existing repo,
main, app.py, Python 3.12, root requirements, empty Secrets, and synthetic data.
Actual Community Cloud build/startup remains unverified until deployment is
explicitly approved. Owner login/connection authorization may be required there.
Before a push, confirm the existing repository name and public scope with the
owner as requested for this review. Before deployment, obtain separate approval.


---

## Authorized final-review publication — 2026-10-25

The owner approved committing and pushing the reviewed changes to the existing
public repository `minghong777/ecommerce-api-automation`. The earlier local-only
review status is historical and superseded by this publication record. The owner
explicitly excluded automatic Streamlit deployment and Google Cloud changes.

Pre-push command: `.venv/bin/python -m pytest -q`.
Actual result: **96 passed in 3.31s**. Reviewed the complete changed-file list,
application/tests, deployment instructions, historical evidence labels, and image
updates. No feature code changed after this successful test run.

The update includes the public credential guard, tested Streamlit dependency
minimum, all-page mobile browser checks, updated README and Upwork copy, Community
Cloud instructions, and the reviewed historical-verification/analytics screenshots.
Historical Google Sheets evidence JSON is unchanged. No actual Google API write,
credential modification, Cloud configuration change, workflow activation, or
scheduled job is part of this publication. Secrets must remain empty for any
future public Streamlit deployment.
