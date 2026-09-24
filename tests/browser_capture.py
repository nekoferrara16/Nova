"""Capture a rendered dashboard without a remote-debugging connection.

Uses Edge's built-in screenshot mode and isolated fixtures; does not automate UI.
"""
import os
import secrets
import socket
import subprocess
import threading
import time
import uuid
from datetime import date
from pathlib import Path

import uvicorn
from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from main.api import create_app, password_hash, token_hash

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'test-results'


def run():
    OUTPUT.mkdir(exist_ok=True)
    run_id = uuid.uuid4().hex
    db_path = OUTPUT / f'capture-{run_id}.sqlite3'
    app = create_app(db_path)
    token = secrets.token_urlsafe(32)
    entry_path = '/capture-' + secrets.token_urlsafe(16)
    reports = []
    app.router.routes = [route for route in app.router.routes if getattr(route, 'path', '') != '/']

    @app.get('/')
    def test_shell():
        html = (ROOT / 'templates' / 'dashboard.html').read_text(encoding='utf-8')
        return HTMLResponse(html.replace('</head>', '<script src="/capture-check.js" defer></script></head>'))

    @app.get('/capture-check.js')
    def capture_check():
        return Response("""
          const captureErrors = [];
          window.addEventListener('error', e => captureErrors.push(e.message));
          window.addEventListener('unhandledrejection', e => captureErrors.push(String(e.reason)));
          const captureTimer = setInterval(async () => {
            if (!document.querySelector('.card-value')) return;
            clearInterval(captureTimer);
            await fetch('/capture-result', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
              viewport:innerWidth, content:document.documentElement.scrollWidth,
              title:document.querySelector('#page-title').textContent,
              metrics:[...document.querySelectorAll('.card-value')].map(e=>e.textContent),errors:captureErrors
            })});
          }, 100);
        """, media_type='application/javascript')

    @app.post('/capture-result')
    async def capture_result(request: Request):
        reports.append(await request.json())
        return {'ok': True}

    # This fixture-only route exists solely in this disposable test process.
    @app.get(entry_path)
    def enter():
        response = RedirectResponse('/')
        response.set_cookie('nova_session', token, httponly=True, samesite='strict')
        return response

    with socket.socket() as probe:
        probe.bind(('127.0.0.1',0))
        port = probe.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,log_level='error'))
    thread = threading.Thread(target=server.run,daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(.05)
    try:
        with app.state.store.connect() as db:
            user = db.execute('INSERT INTO users(username,password_hash) VALUES (?,?)',('Alex Morgan',password_hash('fixture-password-only'))).lastrowid
            db.execute('INSERT INTO sessions VALUES (?,?,?,?)',(token_hash(token),user,secrets.token_urlsafe(24),int(time.time())+600))
            accounts = []
            for name,institution,kind,cents in [('Everyday checking','Everyday bank','checking',1240000),('Rainy day savings','Personal savings','savings',2250000),('Investment account','Brokerage','investment',3650000),('Everyday credit','Credit card','credit',-148250)]:
                accounts.append(db.execute('INSERT INTO accounts(user_id,name,institution,kind,opening_cents,opening_date) VALUES (?,?,?,?,?,?)',(user,name,institution,kind,cents,'2025-01-01')).lastrowid)
            now = date.today()
            for offset in range(5,-1,-1):
                index = now.year*12 + now.month-1-offset
                month = f'{index//12:04d}-{index%12+1:02d}'
                entries = [('Monthly payroll',620000-offset*13000,'Salary','income'),('Rent payment',-185000,'Housing','expense'),('Whole Foods Market',-42835+offset*230,'Groceries','expense'),('Coffee & conversation',-8450+offset*100,'Dining','expense'),('Internet & utilities',-18400,'Utilities','expense'),('Spotify Premium',-1199,'Subscriptions','expense')]
                for description,cents,category,kind in entries:
                    db.execute('INSERT INTO transactions(user_id,account_id,date,description,amount_cents,category,kind) VALUES (?,?,?,?,?,?,?)',(user,accounts[0],month+'-01',description,cents,category,kind))
            for category,cents in [('Groceries',60000),('Dining',25000),('Housing',190000),('Utilities',20000)]:
                db.execute('INSERT INTO budgets VALUES (?,?,?,?)',(user,now.strftime('%Y-%m'),category,cents))
        edge = Path(os.environ.get('PROGRAMFILES(X86)','C:/Program Files (x86)'))/'Microsoft/Edge/Application/msedge.exe'
        for label,width,height in [('desktop',1440,1650),('mobile',500,2500)]:
            screenshot = OUTPUT / f'dashboard-{label}.png'
            profile = OUTPUT / f'capture-profile-{run_id}-{label}'
            args = [str(edge),'--headless','--disable-gpu','--no-first-run','--disable-background-networking',f'--user-data-dir={profile}',f'--window-size={width},{height}','--virtual-time-budget=7000',f'--screenshot={screenshot}',f'http://127.0.0.1:{port}{entry_path}']
            result = subprocess.run(args,capture_output=True,text=True,timeout=45)
            if not screenshot.exists():
                raise RuntimeError(f'No {label} screenshot. {result.stderr[-2000:]}')
            print(f'Saved {screenshot.name}',flush=True)
        assert len(reports) == 2, f'Expected two rendered pages; got {reports}'
        for report in reports:
            assert report['content'] <= report['viewport'], report
            assert not report['errors'], report
            print(f"Rendered checks: {report}",flush=True)
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        db_path.unlink(missing_ok=True)


if __name__ == '__main__':
    run()
