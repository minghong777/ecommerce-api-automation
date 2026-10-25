# Streamlit Community Cloud deployment preparation

**Status:** prepared and locally tested, not publicly deployed. The source repository
already exists at https://github.com/minghong777/ecommerce-api-automation. The owner
authorized publication of the final-review updates on 2026-10-25. Public app deployment
requires separate approval. No scheduler has been activated.

## Exact deployment configuration

| Setting | Value |
|---|---|
| Repository | `minghong777/ecommerce-api-automation` |
| Branch | `main` |
| Main file path | `app.py` |
| Python version | `3.12` (select in Advanced settings) |
| Dependency file | Root `requirements.txt` |
| Streamlit settings | `.streamlit/config.toml` |
| Secrets | **Leave empty** |
| Google credentials | **Do not configure in the public app** |
| Spreadsheet ID / private URL | **Do not configure in the public app** |
| Optional subdomain | Choose an available name only after approval |

Streamlit >=1.66.1 is required by the current layout API usage. The earlier lower
bound 1.45 allowed unsupported `width='stretch'` calls and has been corrected.
`requirements-lock.txt` is a record of the original tested local environment;
Community Cloud installs the root `requirements.txt`, not that snapshot. No
`packages.txt`, Chrome installation, API key, or Playwright dependency is required
for the deployed app. Browser verification tools are optional developer dependencies.

## Public/private boundary

- `app.py` serves only deterministic synthetic commerce data, charts, exports, and
  a Sheets dry-run preview. A product API fetch does not fetch customer orders.
- The web entrypoint stops with a safe message if service-account credential
  environment variables are present. It does not load the credentials or request
  Google tokens. Public deployment settings must still contain **no credentials**.
- No credential upload/input, Google write button, or scheduled callback exists.
- Google Sheets writes remain available in the separate local `src.automation` CLI
  when a trusted private process is explicitly configured and invoked with `--sync`.
- Historical Sheets evidence is dated and sanitized. It is not a live connection
  indicator, and no Google token or private destination belongs in the public app.
- No local absolute path is required by the application. Fixtures resolve relative
  to the source location. Setup examples use repository-relative working directories.

## Checks completed locally

Run from the project root:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m src.automation --dry-run
.venv/bin/python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8502
# In another terminal, optional developer browser check:
.venv/bin/python scripts/browser_check.py --url http://127.0.0.1:8502
```

The final review also installs root requirements in a fresh Python 3.12 virtual
environment and starts a relocated source copy from another working directory.
This checks portability, offline startup, desktop/mobile pages, and downloads
without using a developer's credential environment. See VALIDATION.md for results.

## Manual website steps after explicit publication approval

1. Sign in to https://share.streamlit.io using your own account. If prompted,
   authorize the GitHub connection for the intended repository only.
2. Click **Create app**, then **Yup, I have an app** if that prompt appears.
3. Enter the repository, branch, and entrypoint from the table above.
4. Open **Advanced settings**, select Python **3.12**, and leave **Secrets empty**.
   Do not paste service-account JSON, a private key, or spreadsheet configuration.
5. Review the chosen public URL and click **Deploy** only once deployment is approved.
6. Open the resulting URL in a private/incognito window. Verify the seven pages,
   offline data, mobile layout, and CSV/JSON/Excel downloads without signing in to Google.
7. Confirm the Sheets page is preview-only. Update README and PORTFOLIO.md with the
   real public URL only after the deployed app passes these checks.

These are website login/authorization steps; no new Google Cloud project, service
account, Google OAuth consent, or paid resource is required for the public demo.
The actual cloud build and live URL cannot be verified until deployment is approved.

Official references, checked during final review:

- [Community Cloud deployment](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)
- [Dependency installation](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies)
- [Streamlit 1.45 dataframe API](https://docs.streamlit.io/1.45.0/develop/api-reference/data/st.dataframe)

## Release and scheduling boundary

Review `git status`, the complete diff, tracked files, ignore rules, screenshots,
and secret scan before any future push. The owner confirmed the existing public
repository name and scope for this update on 2026-10-25. This authorization does
not include public app deployment or Google Cloud configuration changes.

Scheduling templates remain inactive under `examples/`, outside
`.github/workflows/`. Cron and a private Sheets job are not part of the public
Streamlit deployment. See PHASE3.md for separately authorized private automation.
