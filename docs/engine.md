# Autonomous maintenance engine (v0.3)

This release replaces the original single-file prompt workflow in the SaaS worker with evidence-ranked code investigation and bounded repair attempts.

## Run

1. Configure the existing SaaS service and worker (see deploy.md). Apply the migration again (`npm run migrate`).
2. Connect a disposable JavaScript/TypeScript repository and select its trusted CI workflow. Configure the OpenAI key and model.
3. Enable automatic proposals. The worker detects failing default-branch CI, collects failed step names and annotations, checks the exact current revision, ranks eligible source paths and reads at most six small regular files. It sends the bounded source context to the provider, which must choose a repair or escalate.
4. Review the resulting rationale and exact source replacement. Approve a draft PR or opt into automatic drafts as described below.
5. The worker polls the chosen GitHub Actions workflow on the repair head. A green workflow is evidence of test success, not proof of application correctness. Merge still requires human authorization, protected-branch rules and the existing stale-base checks.

## Opt-in automatic drafts

Set ENABLE_AUTONOMOUS_DRAFTS=true on both web and worker and explicitly enable autonomous drafts for a project. Keep it disabled for any repository whose repair-branch workflows can access secrets or deploy production. Existing auto-propose consent alone does not grant draft permissions. Automatic drafts only apply to CI incidents; manual requests with an explicit path still require review. An eligible failed repair can trigger one further investigation, subject to daily budget and unchanged base. Both PRs remain visible for review; the system does not delete branches or merge either autonomously.

## Limits

One source file per repair, six context files, 48 KB context source budget, two attempts per automatic incident chain, daily account job cap, no arbitrary command execution by the AI. Tests, workflow files, obvious auth/payment/security/config paths and symlinks are excluded from candidate targets. These are safeguards, not a guarantee that a generated change is safe. Source and failure annotations may contain sensitive data that heuristic detection misses. Production deployment requires a trusted secret-free CI workflow, provider credentials, a database and security review. No native runtime log ingestion or automatic dependency upgrades. HTTP/deployment/security incidents are monitored, not automatically repaired. The engine tests use fake GitHub and model responses; actual external-provider execution requires configured credentials and a test repository.

## Acceptance

Run npm test and GitHub CI. Then intentionally break a disposable application, confirm the incident is recorded, inspect the evidence and proposed patch, open a draft, confirm the selected CI result corresponds to the exact repair head, and exercise a failing repair retry. Validate permission revocation and cross-account isolation. Do not enable live merges before passing these checks.
