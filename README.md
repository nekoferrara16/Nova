# novaFinance

A free-to-run personal finance workspace with persistent accounts, manual entries, CSV statement imports, monthly budgets, and financial summaries. No bank credentials, API keys, paid data services, external fonts, CDN assets, or JavaScript build step are required.

This rebuild replaces the original randomized dashboard with saved, user-specific data. It supports multiple independent users on one server. Start locally; see [online deployment](docs/DEPLOYMENT.md) before hosting it for others.

## Run locally on Windows

Python 3.13 is the tested runtime. From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\run.ps1
```

Open **http://127.0.0.1:8000**, choose **Create a workspace**, and create a username and password of at least 12 characters. No default account or demo financial data is created.

If the virtual environment cannot bootstrap pip, use the system pip to install into it:

```powershell
python -m pip --python .\.venv\Scripts\python.exe install -r requirements.txt
```

If PowerShell does not allow the launcher script, run its command directly:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main.main:app --host 127.0.0.1 --port 8000
```

On macOS/Linux, use `.venv/bin/python` instead. Dependency installation requires access to your approved Python package source; running the installed application requires no internet access.

## Your first weekly review

1. Add checking, savings, cash, investment, credit card, or loan accounts. Set the opening balance at the **start** of a date before the transactions you will enter. For debt accounts, enter a positive amount owed (a negative amount represents an account credit).
2. Import one account's CSV statement. Match the columns, explicitly choose the date format, and review the amount signs. Use either a signed Amount column or positive Debit/Credit columns. A positive signed amount increases the account balance; purchases should be negative, including on credit cards.
3. Review categories and transaction kind before saving. Mark movements between your own accounts, including credit card payments, as **transfer**. A positive **expense** is a refund and reduces spending. Map kind only when the source column contains income/expense/transfer.
4. Set category budgets for the selected month. Use the ledger to search, filter, edit, or delete entries. Imported financial details are fixed to preserve duplicate identities; categories and kind can be corrected. Delete and re-create paired transfers to change them; deleting either leg removes both.
5. Export your records from Settings & exports. A [sample CSV](static/example-transactions.csv) is available for a test account; it contains fabricated September 2026 transactions.

Imports accept UTF-8 or Windows-1252 files up to 3 MB and 10,000 rows, with comma, semicolon, or tab delimiters. The preview is valid for 30 minutes. Any invalid row prevents the entire file from being saved. Rows can be excluded or recategorized during review.

Duplicate detection uses a mapped bank transaction ID when available. Otherwise it uses date, normalized description, amount, and occurrence within the file. Re-importing the same file is safe, and identical rows within a single file are preserved. Identical real transactions in overlapping files are ambiguous without bank IDs. Manual entries are not matched against CSV rows; do not enter and import the same activity twice. Keep the same ID mapping across imports.

## How the numbers work

All persisted monetary amounts are integer USD cents, parsed with decimal arithmetic.

- **Account balance:** signed opening balance plus signed recorded activity through the report date.
- **Net worth:** all active signed account balances, including negative credit/loan balances. This is a recorded book value, not a market valuation.
- **Income:** signed total of income-kind transactions in the selected month.
- **Spending:** negative of expense-kind transactions; positive refunds reduce it.
- **Cash flow:** income minus spending. Transfers affect account balances but neither income nor spending.
- **Cash-flow margin:** cash flow divided by income, only when recorded income is positive. It is not an investment-return calculation.
- **Budget remaining:** category limit minus category net spending, for that month only. It is not spendable cash and budgets do not roll forward automatically.
- **Report date:** the earlier of today and selected month-end. Future transactions remain visible in the ledger but do not enter totals before their dates. Six-month charts reflect only entered history, so an empty month may mean missing data.
- **Recurring candidates:** exact normalized descriptions, seen in each of three recent months, with charge amounts within 20%. These are suggestions, not confirmed subscriptions or forecasts.

There is no automatic bank synchronization, live market pricing, multi-currency conversion, or financial advice engine. [Product roadmap and current limits](docs/ROADMAP.md).

## Storage and recovery

The default database is `data/nova.sqlite3`, relative to the repository, regardless of the launch directory. Data, sessions, and users persist across restarts. It is excluded from Git, but this workspace is inside OneDrive: Git exclusions do not stop cloud synchronization. If you want the database outside a synced folder, set `NOVA_DB` to a private local path before launching. The application creates its parent directory.

```powershell
$env:NOVA_DB = Join-Path $env:LOCALAPPDATA 'novaFinance\nova.sqlite3'
.\run.ps1
```

Use disk encryption and restrict OS access to the database; this application does not encrypt it. Each user's records are scoped in the API, while the operator of the server still controls its storage.

For a complete backup, stop the server and copy the database to a protected location. Restore by stopping the server and replacing its database with that backup. JSON export contains the current user's accounts, transactions, and budgets; it does not contain passwords and is not an automatic restore format. CSV export neutralizes formula-like text for spreadsheet safety.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest tests/test_app.py -q
.\.venv\Scripts\python.exe -m tests.browser_smoke
```

The optional browser workflow check uses an installed Microsoft Edge in headless mode and writes screenshots under ignored `test-results/`. It is designed to verify sign-up, manual entry, CSV import/re-import, budgeting, ledger editing, persistence across refresh, mobile layout, logout, and absence of external requests. This environment's browser policy disables remote debugging, so the Playwright workflow check could not run here.

The API suite passed 19 checks. Standard Edge screenshot mode was used separately to inspect the desktop and narrow layouts, confirm populated report values, and check for script errors and horizontal overflow. Reproduce that check with `python -m tests.browser_capture`. All tests use disposable databases rather than the real workspace database. Rendered screenshots use fabricated fixtures.

## Structure

- `main/api.py`: FastAPI routes, authentication, authorization, and request protections.
- `main/store.py`: SQLite schema and transactional connections.
- `main/finance.py`: financial validation and reporting.
- `main/imports.py`: CSV parsing and duplicate identities.
- `static/`: locally served CSS, JavaScript, icons, and sample CSV.
- `templates/dashboard.html`: accessible app shell and dialogs.
- `tests/`: financial, import, isolation, and browser verification.

The old `charts/` and empty `plaid/` files are legacy prototype artifacts and are no longer imported by the application. There is no Plaid dependency.

The software has no subscription fee or paid API dependency. Public hosting and operations can have costs. The repository does not currently declare an open-source license; distribution/licensing terms remain for the owner to choose.
