# Publication status and hosting preparation

Source publication authorized: https://github.com/minghong777/ecommerce-api-automation

The Streamlit application is not publicly deployed. No scheduler is enabled.

## Prepared application

- Streamlit entrypoint: `app.py`; Python 3.12 tested (minimum Python 3.11).
- Runtime dependencies: `requirements.txt`; installed snapshot: `requirements-lock.txt`.
- Theme/upload limit/telemetry settings: `.streamlit/config.toml`.
- Offline demo works with no credentials, keys, login, or network.
- Public Google Sheets page is preview-only. Do not inject production Google keys
  or a private spreadsheet destination into an unauthenticated public app.
- API responses are validated and bounded; no customer uploads or arbitrary execution.
- Authentication for private Google writes belongs in a trusted CLI environment.

## Release preparation

1. Review changes and run the complete pytest and browser checks from README.
2. Review PORTFOLIO.md, docs/DEMO.md, dated verification evidence, and screenshots.
3. Review staged files before any future commit. Never stage service-account keys,
   `.env`, tokens, protected configuration, private destination URLs, or artifacts/.
   `.gitignore` is a guard, not a substitute for reviewing staged contents. Files
   already tracked by Git remain tracked even after adding an ignore rule.
4. Keep Google credentials outside the repository. Only environment variables in
   an authorized private job should identify the target spreadsheet.
5. Get explicit owner approval before creating/pushing a GitHub repository,
   publishing a Streamlit app, activating a workflow, or installing cron.

## Future hosting choices

Streamlit Community Cloud or a self-hosted Streamlit process may host the public
read-only demo, subject to the host's current terms and limits. Fill README's URL
placeholders only after an approved deployment. This project does not depend on
paid services. Account-level CI quotas and organizational Google key/sharing rules
still apply.

## Scheduling status

Examples remain inactive under examples/. No `.github/workflows` automation or
cron installation is created by this delivery. Use exactly one writer per target
tab set if scheduling is explicitly authorized later. See PHASE3.md for limits,
permissions, unknown-outcome recovery, and safe snapshot replacement semantics.
