"""HTTP endpoints, authentication, and per-user authorization."""
import csv
import hashlib
import hmac
import io
import json
import os
import secrets
import sqlite3
import time
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .finance import ACCOUNT_KINDS, CATEGORIES, money, month_bounds, overview, valid_date
from .imports import inspect_csv, parse_csv
from .store import Store

ROOT = Path(__file__).resolve().parents[1]
MAX_BODY = 4 * 1024 * 1024
SESSION_SECONDS = 12 * 60 * 60


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=60, pattern=r'^[a-zA-Z0-9_.-]+$')
    password: str = Field(min_length=12, max_length=128)


class AccountInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    institution: str = Field(default='', max_length=80)
    kind: Literal['checking', 'savings', 'credit', 'investment', 'loan', 'cash']
    balance: str
    opening_date: str


class TransactionInput(BaseModel):
    account_id: int
    date: str
    description: str = Field(min_length=1, max_length=240)
    amount: str
    category: str
    kind: Literal['income', 'expense', 'transfer']


class TransferInput(BaseModel):
    from_account: int
    to_account: int
    date: str
    amount: str
    description: str = Field(default='Account transfer', min_length=1, max_length=240)


class BudgetInput(BaseModel):
    month: str
    category: str
    amount: str


class CSVInput(BaseModel):
    text: str = Field(max_length=3_000_000)


class PreviewInput(CSVInput):
    account_id: int
    mapping: dict[str, str]
    date_format: str = '%Y-%m-%d'
    invert: bool = False


class ImportEdit(BaseModel):
    row: int
    include: bool = True
    category: str
    kind: Literal['income', 'expense', 'transfer']


class CommitInput(BaseModel):
    draft_id: str
    edits: list[ImportEdit] = Field(default_factory=list, max_length=10000)


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600_000)
    return salt + ':' + digest.hex()


def token_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def clean_text(value):
    result = value.strip()
    if not result:
        raise ValueError('Names and descriptions cannot be blank.')
    return result


def owned_account(db, user_id, account_id):
    row = db.execute('SELECT * FROM accounts WHERE id=? AND user_id=?', (account_id, user_id)).fetchone()
    if not row:
        raise HTTPException(404, 'Account not found.')
    return row


def check_category(category, kind=None):
    if category not in CATEGORIES:
        raise ValueError('Choose a supported category.')
    if kind == 'transfer' and category != 'Transfer':
        raise ValueError('Transfers must use the Transfer category.')
    if kind and kind != 'transfer' and category == 'Transfer':
        raise ValueError('Use transfer kind for the Transfer category.')


def create_app(db_path=None):
    path = db_path or os.getenv('NOVA_DB', str(ROOT / 'data' / 'nova.sqlite3'))
    secure = os.getenv('NOVA_SECURE_COOKIES', '0') == '1'
    configured_origin = os.getenv('NOVA_PUBLIC_ORIGIN', '').rstrip('/')

    @asynccontextmanager
    async def lifespan(app):
        app.state.store = Store(path)
        yield

    app = FastAPI(title='novaFinance', lifespan=lifespan, docs_url=None, redoc_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=os.getenv('NOVA_ALLOWED_HOSTS', '127.0.0.1,localhost,testserver').split(','))
    app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')

    @app.middleware('http')
    async def guard(request, call_next):
        if request.method in ('POST', 'PUT', 'DELETE'):
            expected = configured_origin or str(request.base_url).rstrip('/')
            if request.headers.get('origin') and request.headers['origin'] != expected:
                return JSONResponse({'detail': 'Request origin is not allowed.'}, status_code=403)
            if request.headers.get('sec-fetch-site') == 'cross-site':
                return JSONResponse({'detail': 'Cross-site requests are not allowed.'}, status_code=403)
            if not request.headers.get('content-type', '').startswith('application/json'):
                return JSONResponse({'detail': 'Send JSON data.'}, status_code=415)
            length = request.headers.get('content-length')
            if length and (not length.isdecimal() or int(length) > MAX_BODY):
                return JSONResponse({'detail': 'Request is too large.'}, status_code=413)
            chunks, size = [], 0
            async for chunk in request.stream():
                size += len(chunk)
                if size > MAX_BODY:
                    return JSONResponse({'detail': 'Request is too large.'}, status_code=413)
                chunks.append(chunk)
            request._body = b''.join(chunks)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'"
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        if secure:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        return response

    @app.exception_handler(ValueError)
    async def value_error(request, error):
        return JSONResponse({'detail': str(error)}, status_code=422)

    @app.exception_handler(sqlite3.IntegrityError)
    async def integrity_error(request, error):
        return JSONResponse({'detail': 'That record already exists or conflicts with saved data.'}, status_code=409)

    def session(request):
        token = request.cookies.get('nova_session', '')
        with app.state.store.connect() as db:
            row = db.execute('SELECT s.*, u.username FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>?', (token_hash(token), int(time.time()))).fetchone()
        if not row:
            raise HTTPException(401, 'Sign in to continue.')
        if request.method not in ('GET', 'HEAD') and not hmac.compare_digest(request.headers.get('x-csrf-token', ''), row['csrf']):
            raise HTTPException(403, 'Session verification failed. Refresh and try again.')
        return row

    def issue_session(db, user_id, response):
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
        db.execute('DELETE FROM sessions WHERE expires_at<=?', (int(time.time()),))
        db.execute('INSERT INTO sessions VALUES (?,?,?,?)', (token_hash(token), user_id, csrf, int(time.time()) + SESSION_SECONDS))
        response.set_cookie('nova_session', token, max_age=SESSION_SECONDS, httponly=True, secure=secure, samesite='strict', path='/')
        return csrf

    def throttle(request):
        key, now = request.client.host if request.client else 'local', int(time.time())
        with app.state.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM login_attempts WHERE window_start<?', (now - 900,))
            row = db.execute('SELECT attempts FROM login_attempts WHERE key=?', (key,)).fetchone()
            if row and row['attempts'] >= 30:
                raise HTTPException(429, 'Too many sign-in attempts. Try again in 15 minutes.')
            db.execute('INSERT INTO login_attempts VALUES (?,1,?) ON CONFLICT(key) DO UPDATE SET attempts=attempts+1', (key, now))

    @app.get('/')
    def index():
        return FileResponse(ROOT / 'templates' / 'dashboard.html')

    @app.get('/api/health')
    def health():
        return {'status': 'ok'}

    @app.post('/api/register', status_code=201)
    def register(body: Credentials, request: Request, response: Response):
        if os.getenv('NOVA_ALLOW_REGISTRATION', '1') != '1':
            raise HTTPException(403, 'New account registration is closed.')
        throttle(request)
        with app.state.store.connect() as db:
            user_id = db.execute('INSERT INTO users (username,password_hash) VALUES (?,?)', (body.username, password_hash(body.password))).lastrowid
            csrf = issue_session(db, user_id, response)
        return {'username': body.username, 'csrf': csrf}

    @app.post('/api/login')
    def login(body: Credentials, request: Request, response: Response):
        throttle(request)
        with app.state.store.connect() as db:
            user = db.execute('SELECT * FROM users WHERE username=?', (body.username,)).fetchone()
            stored = user['password_hash'] if user else '00' * 16 + ':' + '00' * 32
            candidate = password_hash(body.password, stored.split(':')[0])
            if not user or not hmac.compare_digest(candidate, stored):
                raise HTTPException(401, 'Username or password is incorrect.')
            csrf = issue_session(db, user['id'], response)
        return {'username': user['username'], 'csrf': csrf}

    @app.post('/api/logout')
    def logout(request: Request, response: Response):
        current = session(request)
        with app.state.store.connect() as db:
            db.execute('DELETE FROM sessions WHERE token_hash=?', (current['token_hash'],))
        response.delete_cookie('nova_session', path='/')
        return {'ok': True}

    @app.get('/api/me')
    def me(request: Request):
        current = session(request)
        return {'username': current['username'], 'csrf': current['csrf'], 'categories': CATEGORIES, 'account_kinds': ACCOUNT_KINDS}

    @app.get('/api/dashboard')
    def dashboard(request: Request, month: str = ''):
        current = session(request)
        with app.state.store.connect() as db:
            return overview(db, current['user_id'], month or date.today().strftime('%Y-%m'))

    @app.post('/api/accounts', status_code=201)
    def add_account(body: AccountInput, request: Request):
        current = session(request)
        opening, cents = valid_date(body.opening_date), money(body.balance)
        if body.kind in ('credit', 'loan'):
            cents = -cents
        with app.state.store.connect() as db:
            ident = db.execute('INSERT INTO accounts (user_id,name,institution,kind,opening_cents,opening_date) VALUES (?,?,?,?,?,?)', (current['user_id'], clean_text(body.name), body.institution.strip(), body.kind, cents, opening)).lastrowid
        return {'id': ident}

    @app.put('/api/accounts/{ident}')
    def edit_account(ident: int, body: AccountInput, request: Request):
        current = session(request)
        opening, cents = valid_date(body.opening_date), money(body.balance)
        if body.kind in ('credit', 'loan'):
            cents = -cents
        with app.state.store.connect() as db:
            owned_account(db, current['user_id'], ident)
            if db.execute('SELECT 1 FROM transactions WHERE account_id=? AND user_id=? AND date<? LIMIT 1', (ident, current['user_id'], opening)).fetchone():
                raise ValueError('Opening date must be on or before all existing transactions for this account.')
            db.execute('UPDATE accounts SET name=?,institution=?,kind=?,opening_cents=?,opening_date=? WHERE id=? AND user_id=?',
                       (clean_text(body.name), body.institution.strip(), body.kind, cents, opening, ident, current['user_id']))
            # A previously reviewed file may no longer match the new opening date.
            db.execute('DELETE FROM import_drafts WHERE account_id=? AND user_id=?', (ident, current['user_id']))
        return {'id': ident}

    @app.delete('/api/accounts/{ident}')
    def delete_account(ident: int, request: Request):
        current = session(request)
        with app.state.store.connect() as db:
            owned_account(db, current['user_id'], ident)
            if db.execute('SELECT 1 FROM transactions WHERE account_id=? AND user_id=? LIMIT 1', (ident, current['user_id'])).fetchone():
                raise ValueError('Only empty accounts can be removed. Delete their transactions first.')
            db.execute('DELETE FROM import_drafts WHERE account_id=? AND user_id=?', (ident, current['user_id']))
            db.execute('DELETE FROM accounts WHERE id=? AND user_id=?', (ident, current['user_id']))
        return {'ok': True}

    def save_transaction(body, request, ident=None):
        current = session(request)
        when, cents = valid_date(body.date), money(body.amount)
        check_category(body.category, body.kind)
        if not cents:
            raise ValueError('A transaction amount cannot be zero.')
        description = clean_text(body.description)
        with app.state.store.connect() as db:
            account = owned_account(db, current['user_id'], body.account_id)
            if when < account['opening_date']:
                raise ValueError('Transaction date cannot precede the opening balance date.')
            if ident is not None:
                old = db.execute('SELECT * FROM transactions WHERE id=? AND user_id=?', (ident, current['user_id'])).fetchone()
                if not old:
                    raise HTTPException(404, 'Transaction not found.')
                if old['transfer_group']:
                    raise ValueError('Delete and re-create a paired transfer to change it.')
                if old['fingerprint'] and (old['account_id'], old['date'], old['amount_cents'], old['description']) != (body.account_id, when, cents, description):
                    raise ValueError('Imported details are fixed for duplicate detection. Change category or kind, or delete and import again.')
                db.execute('UPDATE transactions SET account_id=?,date=?,description=?,amount_cents=?,category=?,kind=? WHERE id=? AND user_id=?', (body.account_id, when, description, cents, body.category, body.kind, ident, current['user_id']))
            else:
                ident = db.execute('INSERT INTO transactions (user_id,account_id,date,description,amount_cents,category,kind) VALUES (?,?,?,?,?,?,?)', (current['user_id'], body.account_id, when, description, cents, body.category, body.kind)).lastrowid
        return {'id': ident}

    @app.post('/api/transactions', status_code=201)
    def add_transaction(body: TransactionInput, request: Request):
        return save_transaction(body, request)

    @app.put('/api/transactions/{ident}')
    def edit_transaction(ident: int, body: TransactionInput, request: Request):
        return save_transaction(body, request, ident)

    @app.delete('/api/transactions/{ident}')
    def delete_transaction(ident: int, request: Request):
        current = session(request)
        with app.state.store.connect() as db:
            row = db.execute('SELECT * FROM transactions WHERE id=? AND user_id=?', (ident, current['user_id'])).fetchone()
            if not row:
                raise HTTPException(404, 'Transaction not found.')
            if row['transfer_group']:
                db.execute('DELETE FROM transactions WHERE transfer_group=? AND user_id=?', (row['transfer_group'], current['user_id']))
            else:
                db.execute('DELETE FROM transactions WHERE id=? AND user_id=?', (ident, current['user_id']))
        return {'ok': True}

    @app.post('/api/transfers', status_code=201)
    def transfer(body: TransferInput, request: Request):
        current = session(request)
        cents, when = money(body.amount), valid_date(body.date)
        if cents <= 0 or body.from_account == body.to_account:
            raise ValueError('Choose two different accounts and a positive amount.')
        group = secrets.token_hex(16)
        with app.state.store.connect() as db:
            for account_id, amount in ((body.from_account, -cents), (body.to_account, cents)):
                account = owned_account(db, current['user_id'], account_id)
                if when < account['opening_date']:
                    raise ValueError('Transfer date cannot precede either opening balance date.')
                db.execute('INSERT INTO transactions (user_id,account_id,date,description,amount_cents,category,kind,transfer_group) VALUES (?,?,?,?,?,?,?,?)', (current['user_id'], account_id, when, clean_text(body.description), amount, 'Transfer', 'transfer', group))
        return {'ok': True}

    @app.put('/api/budgets')
    def budget(body: BudgetInput, request: Request):
        current = session(request)
        month_bounds(body.month)
        check_category(body.category)
        if body.category in ('Transfer', 'Salary', 'Other income', 'Investment income'):
            raise ValueError('Choose a spending category for a budget.')
        cents = money(body.amount)
        if cents < 0:
            raise ValueError('Budget limits cannot be negative.')
        with app.state.store.connect() as db:
            db.execute('INSERT INTO budgets VALUES (?,?,?,?) ON CONFLICT(user_id,month,category) DO UPDATE SET limit_cents=excluded.limit_cents', (current['user_id'], body.month, body.category, cents))
        return {'ok': True}

    @app.delete('/api/budgets/{month}/{category}')
    def delete_budget(month: str, category: str, request: Request):
        current = session(request)
        with app.state.store.connect() as db:
            db.execute('DELETE FROM budgets WHERE user_id=? AND month=? AND category=?', (current['user_id'], month, category))
        return {'ok': True}

    @app.post('/api/import/inspect')
    def inspect(body: CSVInput, request: Request):
        session(request)
        return inspect_csv(body.text)

    @app.post('/api/import/preview')
    def preview(body: PreviewInput, request: Request):
        current = session(request)
        with app.state.store.connect() as db:
            account = owned_account(db, current['user_id'], body.account_id)
            rows, errors = parse_csv(body.text, body.mapping, body.date_format, body.invert, account['opening_date'])
            seen = {r[0] for r in db.execute('SELECT fingerprint FROM transactions WHERE user_id=? AND account_id=? AND fingerprint IS NOT NULL', (current['user_id'], body.account_id))}
            for row in rows:
                row['duplicate'] = row['fingerprint'] in seen
                seen.add(row['fingerprint'])
            draft_id = secrets.token_urlsafe(24)
            db.execute('DELETE FROM import_drafts WHERE expires_at<=? OR user_id=?', (int(time.time()), current['user_id']))
            if not errors:
                db.execute('INSERT INTO import_drafts VALUES (?,?,?,?,?)', (draft_id, current['user_id'], body.account_id, json.dumps(rows), int(time.time()) + 1800))
        return {'draft_id': draft_id if not errors else None, 'rows': rows, 'errors': errors, 'new_count': sum(not r['duplicate'] for r in rows), 'duplicate_count': sum(r['duplicate'] for r in rows)}

    @app.post('/api/import/commit')
    def commit_import(body: CommitInput, request: Request):
        current = session(request)
        with app.state.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            draft = db.execute('SELECT * FROM import_drafts WHERE id=? AND user_id=? AND expires_at>?', (body.draft_id, current['user_id'], int(time.time()))).fetchone()
            if not draft:
                raise HTTPException(404, 'Import preview expired or was already saved. Preview the file again.')
            rows, edits = json.loads(draft['payload']), {e.row: e for e in body.edits}
            valid_rows = {r['row'] for r in rows}
            if len(edits) != len(body.edits) or any(n not in valid_rows for n in edits):
                raise ValueError('Invalid import review rows.')
            added = skipped = 0
            for row in rows:
                edit = edits.get(row['row'])
                if row['duplicate'] or (edit and not edit.include):
                    skipped += 1
                    continue
                category, kind = (edit.category, edit.kind) if edit else (row['category'], row['kind'])
                check_category(category, kind)
                cursor = db.execute('INSERT INTO transactions (user_id,account_id,date,description,amount_cents,category,kind,source,fingerprint) VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(user_id,account_id,fingerprint) DO NOTHING', (current['user_id'], draft['account_id'], row['date'], row['description'], row['amount_cents'], category, kind, 'csv', row['fingerprint']))
                added += cursor.rowcount
                skipped += 1 - cursor.rowcount
            db.execute('DELETE FROM import_drafts WHERE id=?', (body.draft_id,))
        return {'added': added, 'skipped': skipped}

    @app.get('/api/export')
    def export(request: Request):
        current = session(request)
        with app.state.store.connect() as db:
            result = {'format': 'novaFinance', 'version': 1, 'exported_at': date.today().isoformat(), 'currency': 'USD'}
            for table in ('accounts', 'transactions', 'budgets'):
                result[table] = [{k: r[k] for k in r.keys() if k != 'user_id'} for r in db.execute(f'SELECT * FROM {table} WHERE user_id=?', (current['user_id'],))]
        return JSONResponse(result, headers={'Content-Disposition': 'attachment; filename="nova-data.json"'})

    @app.get('/api/export/transactions')
    def export_csv(request: Request):
        current = session(request)
        output = io.StringIO(newline='')
        writer = csv.writer(output)
        writer.writerow(['Date', 'Description', 'Amount', 'Category', 'Kind', 'Account', 'Transaction ID'])
        with app.state.store.connect() as db:
            rows = db.execute('SELECT t.*,a.name account_name FROM transactions t JOIN accounts a ON a.id=t.account_id WHERE t.user_id=? ORDER BY date,id', (current['user_id'],))
            for row in rows:
                def safe(value):
                    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')) else value
                writer.writerow([row['date'], safe(row['description']), f"{row['amount_cents'] / 100:.2f}", row['category'], row['kind'], safe(row['account_name']), row['id']])
        return Response(output.getvalue(), media_type='text/csv', headers={'Content-Disposition': 'attachment; filename="nova-transactions.csv"'})

    return app
