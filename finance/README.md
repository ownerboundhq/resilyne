# Neuravale Finance — desktop pilot 0.3

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

## Continuous desktop office (0.3)

In the desktop launcher, click **Create fictional financial office data**, optionally enable **Schedule fictional browser export every 5 minutes**, then start the worker. The worker automatically reads office.json when present and generates a balanced trial balance, AR/AP aging, a 30-day cash scenario and reminders for explicit supplied deadlines. It stores the original snapshot and result, refreshes once per local calendar day or when the input changes, and exposes the actual output in the dashboard. Data is fictional and single-company; no external financial modifications. Replace office.json only atomically with a fully validated new snapshot in future test cases. A balanced trial balance is not a full financial statement, and the cash scenario is not a prediction. Dates are supplied, not calculated statutory deadlines. Payroll, real tax calculations/filing, assurance and real accounting software control are still unimplemented.

The optional recurring browser job uses a durable lease with retries and a 90-second subprocess timeout. It re-exports the same fictional records; duplicate reconciliation inputs are suppressed. No repeated user prompts are needed after enabling it. It uses headless Chromium and operates only the bundled sandbox. The visible browser button remains available for demonstration. Scheduling requires the local worker and computer to remain running. No startup service or real credentials. Do not use real financial data. Windows connection cleanup was fixed after CI exposed an open SQLite handle.

## Optional unattended Windows startup and Excel pilot

Stop the desktop-owned worker before using the startup task (both use port 8766). From the repository root, with the Windows account that will operate the test company, run:

    powershell -NoProfile -File finance/background.ps1 -Action Install -BrowserDemo
    powershell -NoProfile -File finance/background.ps1 -Action Start

The opt-in task launches the local worker when this user signs in. It does not need the desktop window, does not run when the machine is powered off/asleep, and requires an interactive Windows sign-in. Check with `-Action Status`, stop with `-Action Stop`, remove with `-Action Remove`. Windows execution policy or organization policy may prevent installation; do not bypass organizational security. No task is installed by cloning this repository. The dashboard remains at http://127.0.0.1:8766. Don't start another worker while the scheduled task is running. No SLA; test-only.

On Windows with Microsoft Excel installed, use **Generate report in installed Excel** in the launcher, or `powershell -NoProfile -File finance/excel_export.ps1`. It launches a separate Excel COM instance, writes a new workbook to the workspace reports folder, saves it and closes Excel. Text cells are escaped, and no existing workbook or macros are used. This is real application automation, not arbitrary computer use. No Excel license is supplied. The Excel path and Task Scheduler registration require testing on a real Windows desktop; hosted CI only parses the scripts, not Excel or startup registration.

## Portable Windows download (0.3.1)
The release workflow packages Python, Tkinter and Chromium into an extractable Windows x64 folder. Download the ZIP from [Finance releases](https://github.com/ownerboundhq/resilyne/releases) after a successful build; verify the accompanying SHA-256, extract all files and open NeuravaleFinance.exe. No Python or Git setup is needed. This portable unsigned pilot does not install a startup task. Excel automation requires installed Excel and remains unverified. Use fictional data only.

## Watch the accounting team (0.4.0)

The desktop launcher now has **Start team and watch accounting workflow**. It creates the fictional office snapshot if absent, starts the local worker and opens a separate browser to the bundled practice ledger. The operator navigates, downloads bank and ledger data, identifies two exceptions, posts one explicitly permitted fictional CAD $3 bank fee with a balanced journal, exports the changed ledger and independently verifies that only the authorized entry was added. The remaining CAD $5 mismatch is left for review. Screenshots, source CSVs and the activity trace are saved under workspace/operations. The verified snapshot is queued for reconciliation. This is a fixed allowlisted demonstration, not generalized AI computer use, real ledger posting or live integrations. The practice ledger resets each run; identical inputs are deduplicated in the reconciliation engine. The ongoing worker monitors new local data; the optional recurring browser-export job is still a separate read-only sandbox task.

## Month-end close (0.5.0)

Click **Prepare fictional month-end close**. This seeds an independent fictional company and previous calendar month, then the existing background worker automatically evaluates the new snapshot. Dashboard Month-end close shows period-specific opening and closing trial balances, double-entry/cutoff checks, bank statement opening/movement/closing and reference-level tie-out, AR/AP subledger totals, required inventory/payroll/tax/accrual/depreciation/debt and other review assertions, P&L and balance sheet. It refuses a ready state for missing reviews or discrepancies. Click **Review and seal month-end snapshot** only after inspecting the report. The local fingerprint and original bytes are stored in SQLite; changed input after sealing is flagged. This is a fictional snapshot seal, not an immutable audit log or an external period lock. No real month-end journals, automatic depreciation, inventory valuation, payroll or tax calculations, or external application close are performed. Financial statements are simplified single-month reports from the provided accounts; evidence identifiers and review assertions are supplied rather than verified. The worker prepares any supplied past-month snapshot automatically, not a live recurring connector. Demo totals: revenue CAD 4,200; expense CAD 1,450; net income CAD 2,750; assets CAD 8,200; liabilities CAD 450; equity CAD 7,750.

## Specialist close calculations (0.6.0)

The desktop uses a separate fictional v06 workspace to avoid overwriting earlier sealed periods. **Prepare full specialist month-end close** seeds actual source registers, then the worker calculates FIFO COGS and ending inventory (physical count tie-out), reconciles supplied payroll gross/net/deductions/employer amounts and remittances to separate GL controls, calculates GST/HST from supplied rates and ITC eligibility and reconciles remittances, generates balanced local accrual, prepaid amortization and straight-line depreciation entries, and includes them in the adjusted trial balance, P&L and balance sheet. Four new journal entries in the demo are local derived records, not external postings. Invalid registers or discrepancies block the close. The older review-only fixture remains for regression tests. Source CLI: `python -m finance.month_end --workspace PATH demo --advanced`, then `once`. Expected fictional results: FIFO inventory $96, COGS $124, payroll net $800, payroll closing liabilities $216, GST/HST closing control $215.90, accrual $150, prepaid expense $100, depreciation $10, net income $1,250, assets $9,276, liabilities $1,226, equity $8,050. The payroll amounts, tax rates and eligibility, asset lives and source evidence are supplied; no statutory payroll calculation or tax filing, tax advice, external software posting, physical count collection, or assurance. The inventory pilot assumes ordered whole-unit FIFO transactions and no returns/write-downs; schedules support a restricted single-month scenario with no pre-existing adjustment movements. Remaining cutoff, debt and other-account review gates are still assertions. Do not use real financial data.
