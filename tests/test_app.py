"""Integration tests use isolated disposable databases, never personal data."""
import csv
import io
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main.api import create_app
from main.finance import money

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def client():
    directory = ROOT / 'test-results'
    directory.mkdir(exist_ok=True)
    path = directory / f'test-{uuid.uuid4().hex}.sqlite3'
    with TestClient(create_app(path)) as client:
        yield client
    path.unlink(missing_ok=True)


def register(client, username='alice'):
    response = client.post('/api/register', json={'username': username, 'password': 'correct-horse-battery-123'})
    assert response.status_code == 201, response.text
    client.headers['X-CSRF-Token'] = response.json()['csrf']


def account(client, name='Checking', balance='1000.00', kind='checking', opening='2025-01-01'):
    result = client.post('/api/accounts', json={'name': name, 'balance': balance, 'kind': kind, 'opening_date': opening})
    assert result.status_code == 201, result.text
    return result.json()['id']


def transaction(client, ident, amount, kind='expense', category='Groceries', when='2025-02-04', description='Groceries'):
    return client.post('/api/transactions', json={'account_id':ident,'date':when,'description':description,'amount':amount,'kind':kind,'category':category})


def preview(client, ident, text, **kwargs):
    return client.post('/api/import/preview',json={'account_id':ident,'text':text,'mapping':{'date':'Date','description':'Description','amount':'Amount'},**kwargs})


def dashboard(client):
    response = client.get('/api/dashboard?month=2025-02')
    assert response.status_code == 200, response.text
    return response.json()


def test_authentication_csrf_and_logout(client):
    assert client.get('/').status_code == 200
    assert client.get('/static/app.js').status_code == 200
    assert client.get('/api/dashboard').status_code == 401
    register(client)
    token = client.headers.pop('X-CSRF-Token')
    assert client.post('/api/accounts',json={'name':'Test','balance':'0','kind':'cash','opening_date':'2025-01-01'}).status_code == 403
    client.headers['X-CSRF-Token'] = token
    assert client.post('/api/logout',json={}).status_code == 200
    assert client.get('/api/me').status_code == 401
    assert client.post('/api/login',json={'username':'alice','password':'wrong-password-1234'}).status_code == 401
    assert client.post('/api/login',json={'username':'ALICE','password':'correct-horse-battery-123'}).status_code == 200
    assert client.get('/api/me').headers['cache-control'] == 'no-store'


def test_origin_host_and_registration_controls(client, monkeypatch):
    body = {'username':'alice','password':'correct-horse-battery-123'}
    assert client.post('/api/register',json=body,headers={'Origin':'https://evil.example'}).status_code == 403
    assert client.post('/api/register',content='{}',headers={'Content-Type':'text/plain'}).status_code == 415
    assert client.get('/',headers={'host':'evil.example'}).status_code == 400
    monkeypatch.setenv('NOVA_ALLOW_REGISTRATION','0')
    assert client.post('/api/register',json=body).status_code == 403


def test_user_isolation_for_reads_writes_drafts_and_exports(client):
    register(client)
    alice_account = account(client)
    row = transaction(client,alice_account,'-25').json()['id']
    draft = preview(client,alice_account,'Date,Description,Amount\n2025-02-02,Coffee,-5').json()['draft_id']
    client.post('/api/logout',json={})
    register(client,'bob')
    assert dashboard(client)['accounts'] == []
    assert dashboard(client)['transactions'] == []
    assert client.get('/api/export').json()['accounts'] == []
    assert transaction(client,alice_account,'-100').status_code == 404
    assert client.request('DELETE',f'/api/transactions/{row}',json={}).status_code == 404
    assert client.post('/api/import/commit',json={'draft_id':draft}).status_code == 404
    assert preview(client,alice_account,'Date,Description,Amount\n2025-02-02,Coffee,-5').status_code == 404


def test_money_refunds_transfers_budgets_and_historical_balances(client):
    register(client)
    checking = account(client)
    credit = account(client,'Card','200','credit')
    assert transaction(client,checking,'2000','income','Salary').status_code == 201
    assert transaction(client,checking,'-100').status_code == 201
    assert transaction(client,checking,'20').status_code == 201  # expense refund
    transfer = {'from_account':checking,'to_account':credit,'date':'2025-02-07','amount':'150'}
    assert client.post('/api/transfers',json=transfer).status_code == 201
    assert transaction(client,checking,'-300',when='2099-01-01').status_code == 201
    assert client.put('/api/budgets',json={'month':'2025-02','category':'Groceries','amount':'75'}).status_code == 200
    d = dashboard(client)
    assert d['summary']['income_cents'] == 200000
    assert d['summary']['expense_cents'] == 8000
    assert d['summary']['cash_flow_cents'] == 192000
    assert d['summary']['net_worth_cents'] == 272000
    assert d['summary']['liabilities_cents'] == 5000
    assert d['accounts'][0]['balance_cents'] == 277000
    assert d['budgets'][0]['remaining_cents'] == -500
    assert client.get('/api/dashboard?month=2025-01').json()['summary']['net_worth_cents'] == 80000
    paired = next(t for t in d['transactions'] if t['transfer_group'])
    assert client.request('DELETE',f"/api/transactions/{paired['id']}",json={}).status_code == 200
    assert len(dashboard(client)['transactions']) == 4
    assert dashboard(client)['summary']['net_worth_cents'] == 272000


def test_transfer_failure_rolls_back_both_sides(client):
    register(client)
    ident = account(client)
    response = client.post('/api/transfers',json={'from_account':ident,'to_account':9999,'date':'2025-02-01','amount':'100'})
    assert response.status_code == 404
    assert dashboard(client)['transactions'] == []


def test_import_is_previewed_atomic_and_idempotent(client):
    register(client)
    ident = account(client)
    text = 'Date,Description,Amount\n2025-02-01,Coffee,-5.25\n2025-02-01,Coffee,-5.25\n2025-02-02,Paycheck,1000'
    p = preview(client,ident,text).json()
    assert p['new_count'] == 3
    assert dashboard(client)['transactions'] == []
    assert client.post('/api/import/commit',json={'draft_id':p['draft_id']}).json()['added'] == 3
    assert client.post('/api/import/commit',json={'draft_id':p['draft_id']}).status_code == 404
    p = preview(client,ident,text).json()
    assert p['duplicate_count'] == 3
    assert client.post('/api/import/commit',json={'draft_id':p['draft_id']}).json()['added'] == 0
    assert len(dashboard(client)['transactions']) == 3
    # Same file is meaningful on a separate account.
    other = account(client,'Second')
    assert preview(client,other,text).json()['new_count'] == 3


def test_import_review_classifies_refunds_and_transfers(client):
    register(client)
    ident = account(client)
    text = 'Date,Description,Amount\n2025-02-01,Card payment,-50\n2025-02-02,Refund,20\n2025-02-03,Exclude me,-15'
    p = preview(client,ident,text).json()
    edits = [{'row':2,'kind':'transfer','category':'Transfer'},{'row':3,'kind':'expense','category':'Groceries'},{'row':4,'kind':'expense','category':'Groceries','include':False}]
    response = client.post('/api/import/commit',json={'draft_id':p['draft_id'],'edits':edits})
    assert response.json() == {'added':2,'skipped':1}
    assert dashboard(client)['summary']['expense_cents'] == -2000
    assert dashboard(client)['summary']['income_cents'] == 0


def test_import_errors_never_save_partial_file(client):
    register(client)
    ident = account(client)
    p = preview(client,ident,'Date,Description,Amount\n2025-02-01,Valid,-10\nBAD,Invalid,-10\n2024-01-01,Too early,-1').json()
    assert p['draft_id'] is None
    assert len(p['errors']) == 2
    assert dashboard(client)['transactions'] == []


def test_import_debit_credit_dates_inversion_and_ids(client):
    register(client)
    ident = account(client)
    text = 'Posted;Memo;Debit;Credit;ID\n02/01/2025;One;12.34;;A\n02/02/2025;Two;;50;B'
    mapping = {'date':'Posted','description':'Memo','debit':'Debit','credit':'Credit','external_id':'ID'}
    p = preview(client,ident,text,mapping=mapping,date_format='%m/%d/%Y').json()
    assert [r['amount_cents'] for r in p['rows']] == [-1234,5000]
    client.post('/api/import/commit',json={'draft_id':p['draft_id']})
    changed = text.replace('One','Renamed')
    assert preview(client,ident,changed,mapping=mapping,date_format='%m/%d/%Y').json()['duplicate_count'] == 2
    assert preview(client,ident,'Date,Description,Amount\n2025-02-01,Purchase,20',invert=True).json()['rows'][0]['amount_cents'] == -2000


def test_import_commit_failure_is_atomic_and_draft_can_retry(client):
    register(client)
    ident = account(client)
    p = preview(client,ident,'Date,Description,Amount\n2025-02-01,One,-10\n2025-02-02,Two,-15').json()
    result = client.post('/api/import/commit',json={'draft_id':p['draft_id'],'edits':[{'row':3,'category':'Invalid','kind':'expense'}]})
    assert result.status_code == 422
    assert dashboard(client)['transactions'] == []
    assert client.post('/api/import/commit',json={'draft_id':p['draft_id']}).json()['added'] == 2


def test_edit_and_delete_and_spreadsheet_export(client):
    register(client)
    ident = account(client)
    row = transaction(client,ident,'-5',description='=HYPERLINK("bad")').json()['id']
    body = {'account_id':ident,'date':'2025-02-04','amount':'-7.25','description':'=HYPERLINK("bad")','category':'Dining','kind':'expense'}
    assert client.put(f'/api/transactions/{row}',json=body).status_code == 200
    assert dashboard(client)['summary']['expense_cents'] == 725
    exported = list(csv.DictReader(io.StringIO(client.get('/api/export/transactions').text)))
    assert exported[0]['Description'].startswith("'=")
    assert exported[0]['Amount'] == '-7.25'
    assert client.request('DELETE',f'/api/transactions/{row}',json={}).status_code == 200
    assert dashboard(client)['transactions'] == []


@pytest.mark.parametrize('value',['NaN','Infinity','1.234','not money','9999999999999'])
def test_reject_invalid_money(value):
    with pytest.raises(ValueError):
        money(value)


def test_exact_money():
    assert money('0.29') == 29
    assert money('($1,234.56)') == -123456


def test_dates_and_invalid_values(client):
    register(client)
    ident = account(client)
    assert transaction(client,ident,'-5',when='2024-12-31').status_code == 422
    assert transaction(client,ident,'0').status_code == 422
    assert transaction(client,ident,'-1',category='Transfer').status_code == 422
    assert client.get('/api/dashboard?month=2025-13').status_code == 422
    assert client.get('/api/dashboard?month=bad').status_code == 422


def test_account_correction_and_safe_removal(client):
    register(client)
    ident = account(client)
    draft = preview(client,ident,'Date,Description,Amount\n2025-02-01,Coffee,-5').json()['draft_id']
    body = {'name':'Renamed','balance':'2500','kind':'savings','opening_date':'2025-02-01'}
    assert client.put(f'/api/accounts/{ident}',json=body).status_code == 200
    assert dashboard(client)['summary']['net_worth_cents'] == 250000
    assert client.post('/api/import/commit',json={'draft_id':draft}).status_code == 404
    row = transaction(client,ident,'-20').json()['id']
    assert client.request('DELETE',f'/api/accounts/{ident}',json={}).status_code == 422
    body['opening_date'] = '2025-02-05'
    assert client.put(f'/api/accounts/{ident}',json=body).status_code == 422
    client.request('DELETE',f'/api/transactions/{row}',json={})
    assert client.request('DELETE',f'/api/accounts/{ident}',json={}).status_code == 200
    assert dashboard(client)['accounts'] == []
