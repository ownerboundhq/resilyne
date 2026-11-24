# Resilyne Connect / MCP

## Local Scan (free, no account)
Install Node 22+, clone Resilyne and run npm install --ignore-scripts. Set RESILYNE_PROJECT_ROOT to the absolute path of the app you want to inspect, then run npm run scan. It checks project layout, manifests, lockfiles, conventional tests and CI configuration. It never executes app code or sends local files to a service. It reads package.json only and does not include source or secret values in the report. Unknown checks remain unknown rather than producing a misleading health score.

## MCP stdio server
Use an MCP client that supports local stdio servers, such as a compatible coding agent. Add a server named resilyne with command node, args containing the absolute path to connect/mcp.mjs in the cloned repository, and environment RESILYNE_PROJECT_ROOT pointing at your app. Install dependencies first. Exact client setup syntax varies; this is a generic JSON configuration example:

```json
{
  "mcpServers": {
    "resilyne": {
      "command": "node",
      "args": ["/absolute/path/resilyne/connect/mcp.mjs"],
      "env": {
        "RESILYNE_PROJECT_ROOT": "/absolute/path/my-app"
      }
    }
  }
}
```

Restart the client. Ask it to run scan_local_project and explain the checks requiring attention. No account needed. Do not configure the root to a home directory or unrelated sensitive files.

## Connected tools (requires deployed SaaS)
Sign in to the Resilyne dashboard, connect a repository you own and create a project-scoped agent credential in Connect. Copy it once into your MCP client's private environment (never commit it) as RESILYNE_TOKEN, and set RESILYNE_URL to the actual SaaS HTTPS origin, not GitHub Pages. Restart the MCP server. Tools: get_project_status, get_health_report, list_incidents, list_repairs, request_readiness_scan. The last tool queues a bounded read-only scan and cannot generate repairs, merge or deploy. Agent credentials expire in 30 days and can be revoked from the dashboard. Access to private repository source is intentionally not exposed through MCP.

## Runtime SDK
Create a separate telemetry-scoped credential. On your server only, import createTelemetry from connect/sdk.mjs. Initialize with the configured SaaS origin and token. Call heartbeat(), error('CHECKOUT_FAILED',1) or usage('openai','tokens',1000,2500). The last argument is optional reported cost in millionths of USD. Never send customer identifiers, free-form logs, secrets or payment information. These are best-effort counters, not a billing ledger. Batch locally; max 1000 events per project per day. Never put credentials in frontend bundles. The service does not automatically import cloud bills or collect traces.

## Vault
Run RESILYNE_PROJECT_ROOT=/absolute/app RESILYNE_VAULT_DIR=/private/backups npm run vault. This explicitly creates and verifies a local Git bundle outside the repository; no background upload. Treat bundles as sensitive source and history. Store encrypted off-site and test restores. Git bundles do not include uncommitted files, databases, external LFS objects or provider state. Reverse-patch recovery remains in the existing Repair engine.

## Product scope
Scan: local/connected readiness indicators. Connect: stdio MCP and scoped API. Repair: existing engine. Guard: existing dependency alerts. Pulse: existing HTTP/CI monitoring plus customer-reported heartbeats/error counters. Meter: customer-reported usage and optional cost aggregates. Vault: local Git bundle plus reviewed reverse patches. Native hosting-provider integrations, managed backup storage, automatic cloud cost reconciliation, hosted remote MCP OAuth, and integrations tested in each coding client are not included yet.
