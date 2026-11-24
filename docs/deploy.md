# Deployment

## GitHub App
Create a GitHub App in ownerboundhq. Homepage: final HTTPS origin. User authorization callback: PUBLIC_ORIGIN/auth/callback. Setup URL: PUBLIC_ORIGIN/. Webhook: PUBLIC_ORIGIN/webhooks/github. Use a strong unique webhook secret. Enable OAuth user authorization. Install only on selected repositories.
Permissions: Metadata read, Contents read/write, Pull requests read/write, Actions read, Checks read, Deployments read, Dependabot alerts read if supported. Subscribe to workflow_run, check_run, push, pull_request, deployment_status and Dependabot alert events where supported, plus installation and installation_repositories. No Administration or Workflows write. Personal installations only.
Set app ID, slug, OAuth client ID/secret, webhook secret and PEM private key in secret storage. Never commit keys. User OAuth tokens are discarded after identity retrieval. Worker tokens are short-lived and repository-scoped. Protect the GitHub App key.
Local OAuth can use localhost if permitted; webhooks require public HTTPS. Polling works without webhooks.

## Stripe
Create a recurring price (e.g. CAD 149/month, actual price set in Stripe). Configure STRIPE_PRICE_ID, STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET and customer billing portal. Endpoint PUBLIC_ORIGIN/webhooks/stripe; checkout.session.completed and customer.subscription.created/updated/deleted. Use test mode before BILLING_REQUIRED=true. Do not take live payments before terms, privacy, tax and support are ready.

## Cloud Run
Create dedicated GCP project, Artifact Registry, Cloud SQL PostgreSQL and service accounts. Use Secret Manager for keys and DATABASE_URL, private DB connection/TLS, encrypted backups and least privilege. Container runs non-root.
Illustrative command skeleton: replace PROJECT, REGION, IMAGE, SERVICE_ACCOUNT and configure secret mappings and Cloud SQL network settings before executing.
```sh
gcloud builds submit --tag REGION-docker.pkg.dev/PROJECT/resilyne/app:0.2.0
gcloud run jobs create resilyne-migrate --image IMAGE --region REGION --service-account SERVICE_ACCOUNT --command npm --args run,migrate
gcloud run deploy resilyne-web --image IMAGE --region REGION --service-account SERVICE_ACCOUNT --allow-unauthenticated
gcloud run jobs create resilyne-worker --image IMAGE --region REGION --service-account SERVICE_ACCOUNT --command npm --args run,worker --set-env-vars WORKER_ONCE=true --task-timeout 900s --max-retries 0
```
Set final PUBLIC_ORIGIN, all secrets and Cloud SQL connectivity for service/jobs. Run migration before traffic. Schedule worker job every minute via Cloud Scheduler authenticated as a dedicated invoker. Advisory lock prevents concurrent processing; max 15 jobs per run. Set cost controls and queue monitoring. Commands are a skeleton, not an executed deployment.
Map resilyne.com only after ownership and DNS are confirmed. Update callback/webhook URLs after deployment.

## Hosting
Connect Vercel, Cloud Run, Firebase or Supabase application source and trusted CI. Use a public non-sensitive health endpoint in HEALTH_ALLOWLIST, plus GitHub deployment status from existing CI/CD. No native provider account/API connections yet. Reverse patch goes through review and CI; provider instant rollback is not implemented.

## Operations
Protect branches and use trusted secret-free CI. Review all AI code. Keep merge disabled until end-to-end test succeeds. Set provider budget alerts, retention, backup restoration, key rotation and uptime monitoring. Security review is required before public registration.
