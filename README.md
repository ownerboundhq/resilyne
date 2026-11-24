# Resilyne
**Build it. We keep it running.**

Version 0.2 — SaaS foundation for GitHub-hosted JavaScript/TypeScript applications. Original local pilot: `npm run pilot`. Beta candidate, not a production service.

## Implemented
- GitHub App OAuth login, hashed database sessions, personal-installation ownership checks, repository-scoped installation tokens.
- Multi-account PostgreSQL projects, incident history, durable job queue, per-account limits, audit events.
- Signed GitHub webhooks and periodic polling; CI failure annotations, HTTP probes, Dependabot alerts and GitHub deployment status.
- Optional autonomous single-file repair proposals from eligible CI annotations, human-reviewed draft PRs.
- Selected-workflow verification at PR head SHA, opt-in approved merges, stale-base checks and reverse-patch proposals. Existing customer CI/CD handles deployments.
- Stripe Checkout, subscription portal and signed webhook reconciliation.
- Responsive dashboard, Docker Compose, CI tests, Cloud Run setup guide.

## Start locally
1. Register a GitHub App following [deployment setup](docs/deploy.md).
2. Copy .env.example to .env; configure credentials, strong PostgreSQL password and matching DATABASE_URL.
3. Run `docker compose up --build` and open http://localhost:3000. Or use Node 22+, running PostgreSQL, `npm install --ignore-scripts`, `npm run migrate`, `npm start` and `npm run worker` in a second process.
4. Sign in, install the App on a personal repository, connect using its installation ID and select a trusted CI workflow.
5. Configure OpenAI and Stripe as needed. Leave approved merge disabled until live tests pass.

## Scope and safety
No automatic production merges or direct deployments. Approved draft PRs can trigger customer workflows; use secret-free tests and review generated code. The example restricted Docker workflow is a template, not a universal sandbox. Resilyne verifies reported CI results, not business correctness.

Personal GitHub installations only. HTTP probes use administrator-approved public HTTPS URLs. Deployment tracking uses GitHub events and health endpoints, not native Vercel, GCP, Firebase or Supabase APIs. Dependabot must be enabled. AI proposals are single-file; heuristic redaction cannot guarantee secret removal. Do not connect repositories with secrets in source or annotations. Source is stored in PostgreSQL: use encrypted managed storage, retention and backups before production. No automatic dependency upgrades, cloud-specific rollback, native logs, organization RBAC or production SLA. Deployment is not provisioned by these files.

See [deployment guide](docs/deploy.md), [verification workflow](examples/customer-verification-workflow.yml), [release checklist](docs/release-checklist.md). `npm test` runs unit tests; RESILYNE_DB_TEST=true requires a migrated disposable database. Never run fixtures in production.

## v0.3 autonomous engine
See [engine setup, behavior and limits](docs/engine.md). Apply the schema migration again before running the updated service. Automatic draft creation is separately opt-in and disabled by default. Production merges remain approval-gated.

## v0.4 — Resilyne Connect and Scan
See [MCP, local scanner, runtime SDK and Vault setup](docs/connect.md). Run npm install, npm run migrate and restart services. Local Scan and the local MCP tool work without a hosted backend. Connected features require the SaaS deployment.
