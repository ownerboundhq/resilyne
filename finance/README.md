# Neuravale Finance — desktop pilot 0.2

Mission: a continuously operating accounting team for small and medium businesses.
This release implements an autonomous, deterministic reconciliation worker and an exception-review queue. It does not run the Neuravale language model, operate other applications, connect to real accounts, post entries, make payments, or file taxes.

## Start on Windows (Python 3.11+, no additional packages)

From the repository root, in PowerShell:

    .\.venv\Scripts\python.exe -m finance.worker --workspace "$HOME\Neuravale-finance-demo" demo
    .\.venv\Scripts\python.exe -m finance.worker --workspace "$HOME\Neuravale-finance-demo" serve

Open http://127.0.0.1:8765 in a browser. The worker polls every 30 seconds and the dashboard refreshes every 5 seconds. Ctrl+C stops the worker. Restart the serve command using the same workspace to resume queued work. It works while the process and computer remain running, not while the PC is asleep or powered off. No GPU required. If port 8765 is occupied choose --port 8766.

The sample is fictional: two exact matches, four exceptions, CAD $1.75 difference in net movements. Do not infer a reconciled balance: opening and closing statement balances are not provided.

## Inputs
Use an isolated local test workspace outside the public Git repository. Each batch is a complete snapshot of one CAD bank account and corresponding ledger for the same period. Put bank.csv and ledger.csv into a new folder under workspace/inbox, then create an empty READY file after both files are fully written. Use UTF-8 and the exact header reference,date,amount. ISO dates YYYY-MM-DD, positive inflows and negative outflows, decimal amounts without currency signs or separators. References must identify the same transaction on both sides. See the generated demo. The worker stores input bytes and their combined fingerprint in SQLite; byte-identical pairs are processed only once. Do not edit ready folders; create a new folder for a new or corrected snapshot. Overlapping snapshots are independent and their totals must not be added together. Non-identical corrected inputs generate new batches and do not close old exceptions.

Exact matching requires unique references, identical date and identical integer cents. Duplicates, missing items and differences require human review. Invalid input fails closed. No fuzzy matching or balance verification yet. There is no external side effect.

Review an exception (substitute its actual numeric ID):

    .\.venv\Scripts\python.exe -m finance.worker --workspace "$HOME\Neuravale-finance-demo" ack 1 --reason "Reviewed source documents"

Acknowledgement records a reason; it does not correct a ledger or certify an exception is resolved. Read-only dashboard and CLI are single-user and trust the local OS account. The event log is not tamper-proof. The database is not encrypted by this application. Do not expose the local server or use sensitive live data until authentication, data protection, access controls and retention policies are implemented. Do not commit workspace files, bank statements, receipts or credentials to GitHub.

## Release gates
1. Reconciliation: actual statement balances, account identity, date tolerances, payout splits, reversals, deterministic matching, independent accountant-reviewed test cases.
2. Connectors: per-tenant authorization and read-only imports for QuickBooks Online, Shopify, Wave and Sage; idempotent sync and evidence provenance. Validate each provider's API scope and rate limits.
3. Tool execution: isolated browser worker with allowlisted actions, approved writes, post-action verification, idempotency and recovery. Never give unvalidated model unrestricted credentials or mouse control.
4. Accounting agents: permanent work queues, retry/lease policies, schedules and reconciliation dependencies; bookkeeper, accountant, controller, AP, AR, payroll, treasury, tax and audit-evidence roles. Only the first two pilot functions are implemented.
5. Ledger and tax: double-entry validation, period locks, opening/closing balance checks, GST/HST, payroll, financial statements, year-end and T2 working papers. Certified filing software, authorization and licensed sign-off for regulated assurance where applicable.
6. Production: secure multi-tenant hosting, encryption, backups, monitoring, immutable audit evidence, security testing, independently validated results and incident response. No claim of 24/7 SLA until deployed and monitored.
7. Model: benchmark the original Neuravale model for constrained tool selection against simpler rules and other baselines. It must not generate financial figures or authorize transactions.

No third-party AI API is used by this pilot.

## Windows desktop and visible computer-use pilot (0.2)

From the repository root, run:

    .\.venv\Scripts\python.exe -m pip install -r finance/requirements-desktop.txt
    .\.venv\Scripts\python.exe -m playwright install chromium
    .\.venv\Scripts\python.exe -m finance.desktop

The native Tkinter launcher starts/stops the background reconciliation process, opens the dashboard on port 8766, and launches a separate visible Chromium browser on the same computer. Press **Start local accounting worker**, then **Run visible browser export pilot**, then **Open activity dashboard**. The pilot clicks export buttons in the bundled fictional accounting web application, saves the CSV downloads locally, validates them and queues/reconciles the data. It is a fixed, allowlisted workflow, not general AI or arbitrary desktop control. No live credentials or external accounting sites are used. Chromium installation needs internet; the pilot itself does not. Expected: one exact match, two exceptions, CAD $2.00 net-movement difference. Repeated identical exports produce one reconciliation batch. Logs and data are outside the repository in the Neuravale-finance-desktop-demo folder. The worker stops when the launcher is closed; it needs a powered-on, awake computer. No actual Windows UI/third-party software automation, installer, autostart service, or unrestricted mouse control is implemented. The original language model is not used yet. Do not use real financial records.
