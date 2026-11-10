# Deployment verification

The existing Render/Railway-style commands remain the deployment entry point.
Render's build command installs dependencies, trains the quantile artifacts
from the committed model-ready dataset, and ingests the PostgreSQL serving
database. The running service only loads those artifacts; it never trains
during startup or an API request.
The backend must receive `DATABASE_URL` from the environment and production
must set `DATABASE_REQUIRE_POSTGRES=true`. No database URL or credential is
hardcoded.

Before release:

1. Install backend requirements and verify LightGBM is importable.
2. Train and inspect the quantile manifest in a separate job.
3. Verify all three artifact checksums and model feature schema.
4. Run existing backend tests and the probabilistic edge-case suite.
5. Run the frontend TypeScript build.
6. Run migrations/ingestion only against an isolated PostgreSQL test database.
7. Check `/api/health`, the existing forecast response, and the optional
   quantile fields with artifacts present and absent.
8. Confirm the application does not train models during startup or requests.
9. Run a staging smoke test before any production action.

The current repository still contains a local SQLite fallback and SQLite test
fixtures. That is not evidence of PostgreSQL production verification; a release
report must state whether an isolated PostgreSQL instance was actually tested.
