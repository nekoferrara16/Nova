"""Optional real-browser workflow test: python -m tests.browser_smoke.

Uses an isolated database and test-only account. Requires Playwright and Chrome/Edge.
"""
import os
import socket
import threading
import time
import uuid
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'test-results'
OUTPUT.mkdir(exist_ok=True)
TEMP = OUTPUT / 'browser-temp'
TEMP.mkdir(exist_ok=True)
os.environ['TEMP'] = os.environ['TMP'] = str(TEMP)

import uvicorn
from playwright.sync_api import sync_playwright, expect
from main.api import create_app


def run():
    ident = uuid.uuid4().hex
    db_path = OUTPUT / f'browser-{ident}.sqlite3'
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(db_path), host='127.0.0.1', port=port, log_level='error'))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(.05)
    errors, external = [], []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True, timeout=30000)
            context = browser.new_context(viewport={'width':1440,'height':1100}, device_scale_factor=1)
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('request', lambda request: external.append(request.url) if not request.url.startswith(f'http://127.0.0.1:{port}/') else None)
            page.goto(f'http://127.0.0.1:{port}/')
            expect(page.locator('#auth')).to_be_visible()
            page.locator('#auth-toggle').click()
            page.locator('#auth-form [name=username]').fill('browser_test')
            page.locator('#auth-form [name=password]').fill('browser-test-password-123')
            page.locator('#auth-submit').click()
            expect(page.locator('#app')).to_be_visible()
            page.get_by_role('button',name='Add your first account').click()
            page.locator('#editor-form [name=name]').fill('Everyday checking')
            page.locator('#editor-form [name=institution]').fill('My bank')
            page.locator('#editor-form [name=balance]').fill('5800')
            page.locator('#editor-form [name=opening_date]').fill('2025-01-01')
            page.locator('#editor-form [type=submit]').click()
            expect(page.locator('#editor')).not_to_be_visible()
            expect(page.locator('#page-content')).to_contain_text('Everyday checking')
            page.get_by_role('button',name='Add transaction',exact=True).click()
            page.locator('#editor-form [name=description]').fill('Coffee with a friend')
            page.locator('#editor-form [name=amount]').fill('-12.50')
            page.locator('#editor-form [name=category]').select_option('Dining')
            page.locator('#editor-form [type=submit]').click()
            expect(page.locator('#editor')).not_to_be_visible()
            expect(page.locator('#page-content')).to_contain_text('Coffee with a friend')
            month = date.today().strftime('%Y-%m')
            data = f'Date,Description,Amount\n{month}-01,Monthly payroll,4800\n{month}-01,Rent,-1650\n{month}-01,Groceries,-240\n{month}-01,Internet,-65\n'

            def import_file():
                page.get_by_role('button',name='Import CSV',exact=True).click()
                page.locator('#csv-file').set_input_files({'name':'statement.csv','mimeType':'text/csv','buffer':data.encode()})
                page.locator('#inspect-file').click()
                page.locator('#mapping-form [type=submit]').click()
                expect(page.locator('#review-table')).to_be_visible()

            import_file()
            expect(page.locator('.review-summary')).to_contain_text('4 new transactions')
            page.locator('#commit-import').click()
            expect(page.locator('#import-dialog')).not_to_be_visible()
            expect(page.locator('#page-content')).to_contain_text('Monthly payroll')
            import_file()
            expect(page.locator('.review-summary')).to_contain_text('4 duplicates skipped')
            expect(page.locator('#commit-import')).to_be_disabled()
            page.locator('[data-close=import-dialog]').click()
            page.locator('.nav [data-view=budgets]').click()
            page.get_by_role('button',name='Set a budget',exact=True).click()
            page.locator('#editor-form [name=category]').select_option('Groceries')
            page.locator('#editor-form [name=amount]').fill('500')
            page.locator('#editor-form [type=submit]').click()
            expect(page.locator('#editor')).not_to_be_visible()
            expect(page.locator('#page-content')).to_contain_text('$260.00 remaining')
            # Seed only the isolated browser-test workspace to exercise chart history.
            page.evaluate('''async () => {
              const me = await (await fetch('/api/me')).json();
              const d = await (await fetch('/api/dashboard')).json();
              const headers = {'Content-Type':'application/json','X-CSRF-Token':me.csrf};
              const now = new Date();
              for (let i=1; i<=5; i++) {
                const dt = new Date(now.getFullYear(),now.getMonth()-i,1);
                const day = `${dt.getFullYear()}-${String(dt.getMonth()+1).padStart(2,'0')}-01`;
                for (const [amount,kind,category,description] of [[String(4100+i*140),'income','Salary','Monthly payroll'],[String(-2200-i*65),'expense','Housing','Monthly living costs']]) {
                  const response = await fetch('/api/transactions',{method:'POST',headers,body:JSON.stringify({account_id:d.accounts[0].id,date:day,description,amount,kind,category})});
                  if (!response.ok) throw new Error(await response.text());
                }
              }
            }''')
            page.locator('.nav [data-view=overview]').click()
            page.reload()
            expect(page.locator('#page-content')).to_contain_text('Monthly payroll')
            page.screenshot(path=str(OUTPUT/'dashboard-desktop.png'),full_page=True)
            page.locator('.nav [data-view=transactions]').click()
            page.locator('#search').fill('Coffee')
            expect(page.locator('#ledger-rows tbody tr')).to_have_count(1)
            page.get_by_role('button',name='Edit Coffee with a friend',exact=True).click()
            page.locator('#editor-form [name=category]').select_option('Entertainment')
            page.locator('#editor-form [type=submit]').click()
            expect(page.locator('#editor')).not_to_be_visible()
            expect(page.locator('#ledger-rows')).to_contain_text('Entertainment')
            page.set_viewport_size({'width':390,'height':844})
            expect(page.locator('#mobile-menu')).to_be_visible()
            page.locator('#mobile-menu').click()
            page.locator('.nav [data-view=overview]').click()
            page.screenshot(path=str(OUTPUT/'dashboard-mobile.png'),full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Mobile page overflows horizontally'
            page.locator('#mobile-menu').click()
            page.locator('#logout').click()
            expect(page.locator('#auth')).to_be_visible()
            assert not errors, errors
            assert not external, external
            context.close()
            browser.close()
        print('Browser checks passed: signup, accounts, manual entry, CSV mapping/preview/import, duplicate detection, budgets, transaction edit/search, persisted reload, responsive layout, logout, no external requests.')
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        db_path.unlink(missing_ok=True)


if __name__ == '__main__':
    run()
