# Implementation plan
1. Define validated normalized entities with integer-cent money and deterministic offline fixtures.
2. Implement bounded paginated HTTP retrieval, payload validation, and explicit source provenance.
3. Share filtering, financial calculations, and safe in-memory reporting across every UI page.
4. Build six Streamlit workspaces with responsive charts and clear synthetic-data disclosures.
5. Verify business rules, API failures, exports, offline startup, and desktop/mobile browser behavior.

No deployment, repository push, paid services, credentials, or scheduled jobs.

## Phase 3
1. Reuse the existing report pipeline in a standalone CLI with explicit source/filter options.
2. Load service-account credentials securely with google-auth; use the official Sheets v4 REST API.
3. Atomically replace only dedicated, ownership-marked tabs; refuse existing unmanaged tabs.
4. Add credential-free dry-run previews and safe public-demo integration status.
5. Add mocked sync/auth/retry tests, scheduling templates, and updated verification records.
