"""Explicit, reviewable CSV parsing with stable per-account import identities."""
import csv
import hashlib
import io
from collections import Counter
from datetime import datetime
from .finance import CATEGORIES, money, suggest_category

ALIASES = {
    'date': ['date', 'transaction date', 'posted date', 'posting date'],
    'description': ['description', 'memo', 'merchant', 'name', 'payee', 'transaction description'],
    'amount': ['amount', 'transaction amount', 'net amount'],
    'debit': ['debit', 'debits', 'withdrawal', 'withdrawals'],
    'credit': ['credit', 'credits', 'deposit', 'deposits'],
    'category': ['category'], 'external_id': ['transaction id', 'id', 'reference'],
    'kind': ['kind', 'type'],
}


def read_csv(text):
    if not text.strip():
        raise ValueError('The CSV file is empty.')
    sample = text.lstrip('\ufeff')
    try:
        dialect = csv.Sniffer().sniff(sample[:8192], delimiters=',;\t')
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(sample), dialect=dialect)
    headers = reader.fieldnames or []
    if not headers or len(headers) != len(set(headers)) or any(not h.strip() for h in headers):
        raise ValueError('CSV headers must be present, unique, and nonempty.')
    if len(headers) > 60:
        raise ValueError('A CSV may have at most 60 columns.')
    try:
        rows = list(reader)
    except csv.Error:
        raise ValueError('The CSV could not be read. Check its quoting and field lengths.') from None
    if not rows:
        raise ValueError('The CSV contains headers but no transactions.')
    if len(rows) > 10000:
        raise ValueError('Import at most 10,000 rows at a time.')
    return headers, rows


def inspect_csv(text):
    headers, rows = read_csv(text)
    lookup = {h.strip().casefold(): h for h in headers}
    suggested = {key: next((lookup[a] for a in aliases if a in lookup), '') for key, aliases in ALIASES.items()}
    return {'headers': headers, 'suggested': suggested, 'sample': rows[:4], 'row_count': len(rows)}


def parse_csv(text, mapping, date_format, invert, opening_date):
    headers, rows = read_csv(text)
    if date_format not in ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%m/%d/%y'):
        raise ValueError('Select a supported date format.')
    for key in ('date', 'description'):
        if not mapping.get(key):
            raise ValueError(f'Map a {key} column.')
    if not mapping.get('amount') and not (mapping.get('debit') or mapping.get('credit')):
        raise ValueError('Map an amount column, or debit and/or credit columns.')
    if any(value and value not in headers for value in mapping.values()):
        raise ValueError('A mapped column is missing from the file.')
    if mapping.get('amount') and (mapping.get('debit') or mapping.get('credit')):
        raise ValueError('Choose either a signed amount or debit/credit columns, not both.')
    used = [v for v in mapping.values() if v]
    if len(used) != len(set(used)):
        raise ValueError('Each column can only be mapped once.')
    result, errors, occurrences = [], [], Counter()
    for index, row in enumerate(rows, start=2):
        def cell(key):
            return (row.get(mapping.get(key)) or '').strip()
        try:
            if None in row:
                raise ValueError('Too many columns; check the delimiter or quoting.')
            when = datetime.strptime(cell('date'), date_format).date().isoformat()
            if when < opening_date:
                raise ValueError('Date is before the account opening balance date.')
            description = cell('description')
            if not description or len(description) > 240:
                raise ValueError('Description must contain 1–240 characters.')
            if mapping.get('amount'):
                amount = money(cell('amount')) * (-1 if invert else 1)
            else:
                debit, credit = money(cell('debit') or '0'), money(cell('credit') or '0')
                if debit < 0 or credit < 0 or (debit and credit):
                    raise ValueError('Debit/credit columns must be positive and only one may be nonzero per row.')
                amount = credit - debit
            if not amount:
                raise ValueError('Zero-value transactions cannot be imported.')
            kind = cell('kind').casefold() or ('income' if amount > 0 else 'expense')
            if kind not in ('income', 'expense', 'transfer'):
                raise ValueError('Kind must be income, expense, or transfer; unmap other bank type columns.')
            category = cell('category') or suggest_category(description, amount)
            if category not in CATEGORIES:
                category = 'Uncategorized'
            if kind == 'transfer':
                category = 'Transfer'
            elif category == 'Transfer':
                raise ValueError('A Transfer category requires transfer kind.')
            external_id = cell('external_id')
            identity = f'{when}|{" ".join(description.casefold().split())}|{amount}'
            occurrences[identity] += 1
            identity = 'id:' + external_id if external_id else identity + f'|{occurrences[identity]}'
            fingerprint = hashlib.sha256(identity.encode()).hexdigest()
            result.append({'row': index, 'date': when, 'description': description, 'amount_cents': amount,
                           'category': category, 'kind': kind, 'fingerprint': fingerprint})
        except (ValueError, csv.Error) as error:
            errors.append({'row': index, 'error': str(error)})
    return result, errors
