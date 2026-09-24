"""Deterministic financial calculations shared by the API and tests."""
import calendar
import re
from datetime import date
from decimal import Decimal, InvalidOperation

CATEGORIES = ['Housing', 'Groceries', 'Dining', 'Transportation', 'Utilities',
              'Healthcare', 'Shopping', 'Entertainment', 'Subscriptions',
              'Education', 'Travel', 'Insurance', 'Taxes', 'Salary',
              'Investment income', 'Other income', 'Uncategorized', 'Transfer']
ACCOUNT_KINDS = ['checking', 'savings', 'credit', 'investment', 'loan', 'cash']


def money(value):
    text = str(value).strip().replace('$', '').replace(',', '')
    if text.startswith('(') and text.endswith(')'):
        text = '-' + text[1:-1]
    try:
        number = Decimal(text)
        if not number.is_finite() or abs(number) > Decimal('999999999999'):
            raise ValueError('Amount is outside the supported range.')
        cents = number * 100
        if cents != cents.to_integral_value():
            raise ValueError('Amounts must have at most two decimal places.')
        return int(cents)
    except InvalidOperation:
        raise ValueError('Enter a valid dollar amount.') from None


def valid_date(value):
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('Use a date in YYYY-MM-DD format.')
    return date.fromisoformat(value).isoformat()


def month_bounds(month):
    if not re.fullmatch(r'\d{4}-\d{2}', month):
        raise ValueError('Use a month in YYYY-MM format.')
    first = date.fromisoformat(month + '-01')
    return first.isoformat(), first.replace(day=calendar.monthrange(first.year, first.month)[1]).isoformat()


def suggest_category(description, amount):
    text = description.casefold()
    groups = {
        'Salary': ['payroll', 'salary', 'direct deposit'],
        'Groceries': ['grocery', 'groceries', 'trader joe', 'whole foods', 'safeway', 'kroger'],
        'Dining': ['restaurant', 'coffee', 'cafe', 'doordash', 'chipotle'],
        'Transportation': ['uber', 'lyft', 'gas station', 'shell', 'chevron', 'parking'],
        'Subscriptions': ['netflix', 'spotify', 'hulu', 'adobe'],
        'Utilities': ['electric', 'water bill', 'internet', 'comcast'],
        'Housing': ['rent', 'mortgage'],
        'Healthcare': ['pharmacy', 'hospital', 'clinic'],
    }
    for category, keywords in groups.items():
        if any(word in text for word in keywords):
            return category
    return 'Other income' if amount > 0 else 'Uncategorized'


def overview(db, user_id, month):
    start, end = month_bounds(month)
    if not 1901 <= int(month[:4]) <= 9998:
        raise ValueError('Reporting years must be between 1901 and 9998.')
    # An open month stops at today; future-dated entries remain in the ledger.
    as_of = min(end, date.today().isoformat())
    accounts = [dict(r) for r in db.execute('SELECT * FROM accounts WHERE user_id=? ORDER BY id', (user_id,))]
    rows = [dict(r) for r in db.execute(
        'SELECT t.*, a.name account_name FROM transactions t JOIN accounts a ON a.id=t.account_id '
        'WHERE t.user_id=? ORDER BY t.date DESC, t.id DESC', (user_id,))]
    actual = [r for r in rows if r['date'] <= as_of]
    selected = [r for r in actual if start <= r['date'] <= end]
    income = sum(r['amount_cents'] for r in selected if r['kind'] == 'income')
    spending = -sum(r['amount_cents'] for r in selected if r['kind'] == 'expense')
    category_spend = {}
    for row in selected:
        if row['kind'] == 'expense':
            category_spend[row['category']] = category_spend.get(row['category'], 0) - row['amount_cents']
    assets = liabilities = liquid = 0
    for account in accounts:
        active = account['opening_date'] <= as_of
        balance = account['opening_cents'] + sum(r['amount_cents'] for r in actual if r['account_id'] == account['id']) if active else 0
        account['balance_cents'] = balance
        account['active'] = active
        assets += max(balance, 0)
        liabilities += max(-balance, 0)
        if account['kind'] in ('checking', 'savings', 'cash'):
            liquid += balance
    budgets = [dict(r) for r in db.execute('SELECT * FROM budgets WHERE user_id=? AND month=? ORDER BY category', (user_id, month))]
    for budget in budgets:
        budget['spent_cents'] = category_spend.get(budget['category'], 0)
        budget['remaining_cents'] = budget['limit_cents'] - budget['spent_cents']
    trend = []
    year, mon = map(int, month.split('-'))
    for offset in range(5, -1, -1):
        index = year * 12 + mon - 1 - offset
        label = f'{index // 12:04d}-{index % 12 + 1:02d}'
        left, right = month_bounds(label)
        stop = min(right, date.today().isoformat())
        items = [r for r in actual if left <= r['date'] <= stop]
        trend.append({'month': label,
                      'income_cents': sum(r['amount_cents'] for r in items if r['kind'] == 'income'),
                      'expense_cents': -sum(r['amount_cents'] for r in items if r['kind'] == 'expense')})
    insights = []
    uncategorized = sum(1 for r in selected if r['category'] == 'Uncategorized')
    if uncategorized:
        insights.append({'title': 'A little clarity goes a long way', 'detail': f'{uncategorized} transactions need a category. Review them in your ledger.', 'tone': 'amber'})
    over = [b for b in budgets if b['remaining_cents'] < 0]
    if over:
        insights.append({'title': 'Budgets to revisit', 'detail': ', '.join(b['category'] for b in over) + ' exceeded the monthly limit.', 'tone': 'amber'})
    if income > 0:
        insights.append({'title': 'Your cash-flow margin', 'detail': f'{(income - spending) / income:.0%} of recorded income remains after recorded expenses this month.', 'tone': 'green' if income >= spending else 'amber'})
    if not accounts:
        insights.append({'title': 'Make room for the full picture', 'detail': 'Add your accounts, then import a statement or record your first transaction.', 'tone': 'green'})
    if accounts and not selected:
        insights.append({'title': 'A fresh page', 'detail': 'No posted transactions for this month yet. Import a statement to start seeing your cash flow.', 'tone': 'green'})
    # Recurring candidates require activity in at least three distinct months.
    grouped = {}
    for row in actual:
        if row['kind'] == 'expense' and row['amount_cents'] < 0:
            key = re.sub(r'\s+', ' ', row['description'].strip().casefold())
            grouped.setdefault(key, []).append(row)
    recurring = []
    recent_floor = trend[-3]['month']
    for values in grouped.values():
        recent = [r for r in values if recent_floor <= r['date'][:7] <= month]
        periods = {r['date'][:7] for r in recent}
        amounts = [abs(r['amount_cents']) for r in recent]
        if len(periods) >= 3 and max(amounts) <= min(amounts) * 1.2:
            recurring.append({'description': recent[0]['description'], 'amount_cents': round(sum(amounts) / len(amounts)), 'months': len(periods)})
    return {'month': month, 'as_of': as_of, 'accounts': accounts, 'transactions': rows,
            'summary': {'net_worth_cents': assets - liabilities, 'assets_cents': assets,
                        'liabilities_cents': liabilities, 'liquid_cents': liquid,
                        'income_cents': income, 'expense_cents': spending, 'cash_flow_cents': income - spending,
                        'savings_rate': round((income - spending) / income * 100, 1) if income > 0 else None,
                        'budget_remaining_cents': sum(b['remaining_cents'] for b in budgets)},
            'categories': [{'category': k, 'amount_cents': v} for k, v in sorted(category_spend.items(), key=lambda x: -x[1])],
            'budgets': budgets, 'trend': trend, 'insights': insights, 'recurring': recurring}
