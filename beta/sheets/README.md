# Resilyne private live Sheets beta

Workbook: https://docs.google.com/spreadsheets/d/14H90NRcl95RbdNcGRyF22VspGiiPIc1JTYbgrhWpxAc/edit

1. Open the workbook as the owner. Extensions → Apps Script.
2. Replace the default Code.gs with the complete contents of [Code.gs](./Code.gs). Save.
3. Reload the workbook. In Applications, enable the example app in D4 (or enter a public HTTPS URL you own/are authorized to monitor). Maximum five rows, A4:D8. Use a direct URL returning 2xx, not a redirect. No query strings or credentials.
4. Resilyne → Start monitoring. Review Google's authorization screen and approve only if you trust the source. This installs a five-minute time trigger and runs the first cycle. Resilyne → Run checks now is available while enabled. Resilyne → Stop monitoring removes this owner's trigger and pauses checks. Unchecking Control B5 pauses subsequent cycles.

Actual signals: HTTP response status and latency, two consecutive failures to mark DOWN and two successes to mark recovery; most recent GitHub workflow run (not all CI); optional read-only Dependabot alert count. Events records observed changes. No fabricated health values. Times are UTC. Last readings may be stale when checks are paused, blocked, or quota-limited.

Optional security: only in a private, single-owner script, set GITHUB_READ_TOKEN in Apps Script Project Settings → Script properties. Use a fine-grained expiring token restricted to selected repos, Actions read and Dependabot alerts read, metadata read. Never put tokens in cells, source, chat or logs. Editors of the script can read/use script properties; do not share with untrusted editors. Tokenless public GitHub requests may be rate-limited. An inaccessible alerts API is NOT ASSESSED, not zero alerts. Count is bounded to 100. No full security scan.

Limits: Apps Script scheduling and quotas are best-effort; not a 24/7 SLA. This is a personal read-only beta, not multi-tenant SaaS. Use only trusted public endpoints you own or are authorized to monitor; hostname checks do not establish ownership or prevent all DNS-related SSRF risks. No automated patches, deployment rollback, managed backups, billing, real GitHub App installation or production writes. No data beyond requests to the chosen endpoints and GitHub is transmitted by this script. No automatic AI calls. Only the workbook owner should install the trigger. Keep the workbook private. Avoid modifying rows while a check is running. Apps Script installation and Google OAuth approval are required; neither is accomplished by creating the workbook. Node tests mock selected helpers, not the Apps Script runtime.
