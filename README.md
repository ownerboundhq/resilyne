# Resilyne

**Build it. We keep it running.**

An early, single-operator pilot of autonomous software maintenance. This is executable software, not a production SaaS. No simulated monitoring metrics.

## Run locally

Requires Node.js 22+. No npm dependencies.

1. Copy .env.example to .env and fill in GITHUB_REPO and GITHUB_TOKEN. Use a fine-grained GitHub token restricted to the monitored repository: Metadata read, Actions read, Contents read/write, Pull requests read/write. Never commit it.
2. Optionally set HEALTH_URL to a trusted HTTPS endpoint that represents application health.
3. Optionally set OPENAI_API_KEY and OPENAI_MODEL for repair proposals. Selected source and incident summary are sent to OpenAI only when requested. Do not select confidential or secret-bearing files without appropriate authorization.
4. Run `npm test`, then `npm start`.
5. Open http://127.0.0.1:3000 (or configured PORT).

## What works in this pilot

- Scheduled and manual GitHub Actions monitoring of the default branch (latest 30 runs).
- HTTPS endpoint checks; persistent incident records and observed recovery.
- Explicit selection of a JavaScript/TypeScript source file for AI repair suggestions.
- Local review of original and proposed source, reject or approve creation of a draft GitHub PR.
- Stale-base guard, deterministic repair branch, no automatic merging/deploying.
- Local JSON persistence in .data; single process only.

## Important limitations

No real-time logs, source-wide diagnosis, automated test execution, deploy/rollback, security scanning, multi-user accounts, GitHub App OAuth, billing, or cloud deployment yet. A failed CI summary alone may be insufficient for a useful repair. A draft PR does not prove a fix works. Run the repository's tests and inspect the diff before merging. The simple secret detection is not comprehensive. Source/proposals are stored locally in plaintext; protect the machine and .data directory. Never expose this localhost pilot to the public internet, reverse proxy or other users. The health endpoint is operator-controlled and trusted; do not accept arbitrary user URLs. The background poll only runs while the process is running. Provider calls can incur charges. Production requires explicit repository ownership validation and isolated workers.

## Next release gates

1. GitHub App with least-privilege installation tokens, verified webhooks and OAuth session authentication; tenant isolation and encrypted secrets.
2. Durable queue and database, rate limits, budget caps, audit trail and incident deduplication across replicas.
3. Redacted CI/log evidence and targeted retrieval; isolated no-secret test sandbox with bounded resources and network restrictions.
4. Mandatory test gates and patch review; rollback and deployment integrations only after safe staging verification.
5. Security/dependency monitoring, billing and usage metering, production reliability and security review.

See public/index.html for the branded operator interface. The pilot is intentionally limited to one repository and one local operator.
