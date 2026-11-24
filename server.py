#!/usr/bin/env python3
"""Alipen Solutions Agency Ltd website and quote-request service."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import http.server
import json
import html
import logging
import os
import re
import secrets
import socketserver
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict, deque
from hashlib import sha256
from email.utils import parseaddr
from http.cookies import CookieError, SimpleCookie
from pathlib import Path
from zoneinfo import ZoneInfo

from invoice_documents import invoice_pdf

try:
    import psycopg
except ImportError:  # Allows static pages and syntax checks before dependencies are installed.
    psycopg = None

try:
    from argon2 import PasswordHasher
    from argon2.exceptions import InvalidHashError, VerificationError
except ImportError:  # Login remains disabled until production dependencies are installed.
    PasswordHasher = None
    InvalidHashError = VerificationError = Exception


DIRECTORY = Path(__file__).resolve().parent


def load_local_env():
    """Load simple KEY=value entries from a local .env without overriding process env."""
    env_path = DIRECTORY / '.env'
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_local_env()
PORT = int(os.environ.get('PORT', '3000'))
HOST = '0.0.0.0'
DATABASE_URL = os.environ.get('DATABASE_URL', '').strip()
SITE_URL = os.environ.get('SITE_URL', '').rstrip('/')
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL', '').rstrip('/')
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', '').strip()
MAIL_FROM = os.environ.get('MAIL_FROM', '').strip()
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '').strip()
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', '').strip()
ADMIN_PASSWORD_HASH = os.environ.get('ADMIN_PASSWORD_HASH', '').strip()
_password_hasher = PasswordHasher() if PasswordHasher is not None else None
MAX_REQUEST_BYTES = 64 * 1024
RATE_LIMIT_REQUESTS = 8
RATE_LIMIT_WINDOW_SECONDS = 15 * 60
ADMIN_LOGIN_LIMIT = 5
ADMIN_SESSION_SECONDS = 8 * 60 * 60
ADMIN_USERNAME_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{2,119}$')
_rate_limit_lock = threading.Lock()
_request_times = defaultdict(deque)
_admin_login_lock = threading.Lock()
_admin_login_attempts = defaultdict(deque)
_admin_sessions_lock = threading.Lock()
_admin_sessions = {}

STATIC_ROOT_FILES = {
    'index.html', 'products.html', 'product-detail.html', 'about.html',
    'contact.html', 'admin-login.html', 'styles.css', 'app.js', 'products.js', 'script.js',
    'admin.css', 'admin.js', 'admin-diagnostics-loader.js', 'admin-diagnostics.js',
}
ADMIN_STATUSES = {'received', 'in_progress', 'completed'}
ADMIN_STATUSES.update({'won', 'lost'})
BUSINESS_TIMEZONE = ZoneInfo('Africa/Nairobi')
INVOICE_TEMPLATES = {
    'docx': (DIRECTORY / 'private_documents' / 'alipen-invoice-template.docx',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
    'pdf': (DIRECTORY / 'private_documents' / 'alipen-invoice-template.pdf', 'application/pdf'),
}
ADMIN_QUOTE_COLUMNS = (
    'reference', 'name', 'facility', 'facility_type', 'county', 'phone',
    'email', 'items', 'requirements', 'status', 'created_at',
    'follow_up_date', 'follow_up_note', 'follow_up_completed',
)
INVOICE_COLUMNS = (
    'id', 'invoice_number', 'quote_reference', 'customer_name', 'customer_email',
    'company_name', 'customer_address', 'invoice_date', 'due_date', 'status',
    'currency', 'subtotal', 'discount_amount', 'tax_rate', 'tax_amount', 'total',
    'notes', 'payment_instructions', 'amount_paid', 'payment_date',
    'payment_reference', 'payment_note', 'created_by', 'created_at', 'updated_at',
)
INVOICE_ITEM_COLUMNS = ('id', 'product_slug', 'name', 'description', 'quantity', 'unit_price', 'line_total')
INVOICE_COLUMN_SQL = ', '.join(INVOICE_COLUMNS)
INVOICE_ITEM_COLUMN_SQL = ', '.join(INVOICE_ITEM_COLUMNS)
INVOICE_NUMBER_SEQUENCE = 'alipen_invoice_number_seq'
_catalogue_product_slugs = None
STATIC_EXTENSIONS = {
    '.html', '.css', '.js', '.png', '.jpg', '.jpeg', '.webp', '.gif',
    '.svg', '.ico', '.woff', '.woff2', '.ttf',
}
EMAIL_RE = re.compile(r'^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$')

logger = logging.getLogger(__name__)


class DatabaseUnavailable(RuntimeError):
    pass


def database_connection():
    if not DATABASE_URL:
        raise DatabaseUnavailable('DATABASE_URL is not configured')
    if psycopg is None:
        raise DatabaseUnavailable('PostgreSQL driver is not installed; run pip install -r requirements.txt')
    try:
        return psycopg.connect(DATABASE_URL, connect_timeout=8)
    except Exception as exc:
        raise DatabaseUnavailable('Could not connect to PostgreSQL') from exc


def init_database():
    with database_connection() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS quote_requests (
                id BIGSERIAL PRIMARY KEY,
                reference VARCHAR(20) UNIQUE NOT NULL,
                name VARCHAR(120) NOT NULL,
                facility VARCHAR(180) NOT NULL,
                facility_type VARCHAR(100),
                county VARCHAR(100),
                phone VARCHAR(50) NOT NULL,
                email VARCHAR(180) NOT NULL,
                requirements TEXT,
                items JSONB,
                status VARCHAR(30) DEFAULT 'received',
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                ip_address VARCHAR(64)
            )
        ''')
        # Additive migration for secondary administrator accounts. Existing quote data is untouched.
        conn.execute('''
            CREATE TABLE IF NOT EXISTS admin_users (
                id BIGSERIAL PRIMARY KEY,
                username VARCHAR(120) NOT NULL,
                password_hash TEXT NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS admin_users_username_lower_unique
            ON admin_users (LOWER(username))
        ''')
        # Additive quote workflow fields; existing quote records and statuses remain intact.
        conn.execute('ALTER TABLE quote_requests ADD COLUMN IF NOT EXISTS follow_up_date DATE')
        conn.execute('ALTER TABLE quote_requests ADD COLUMN IF NOT EXISTS follow_up_note TEXT')
        conn.execute('ALTER TABLE quote_requests ADD COLUMN IF NOT EXISTS follow_up_completed BOOLEAN NOT NULL DEFAULT FALSE')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS quote_notes (
                id BIGSERIAL PRIMARY KEY,
                quote_reference VARCHAR(20) NOT NULL REFERENCES quote_requests(reference) ON DELETE CASCADE,
                author_username VARCHAR(120) NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS quote_requests_follow_up_idx ON quote_requests (follow_up_date) WHERE follow_up_completed = FALSE')
        conn.execute('CREATE INDEX IF NOT EXISTS quote_requests_status_created_idx ON quote_requests (status, created_at DESC)')
        conn.execute('CREATE INDEX IF NOT EXISTS quote_notes_reference_created_idx ON quote_notes (quote_reference, created_at)')
        # Additive, idempotent invoice migration. The global sequence allocates
        # unique invoice numbers safely across concurrent admin requests.
        conn.execute(f'CREATE SEQUENCE IF NOT EXISTS {INVOICE_NUMBER_SEQUENCE} START WITH 1')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS invoices (
                id BIGSERIAL PRIMARY KEY,
                invoice_number VARCHAR(40) NOT NULL UNIQUE,
                quote_reference VARCHAR(20) REFERENCES quote_requests(reference) ON DELETE SET NULL,
                customer_name VARCHAR(180) NOT NULL,
                customer_email VARCHAR(180) NOT NULL DEFAULT '',
                company_name VARCHAR(180) NOT NULL DEFAULT '',
                customer_address TEXT NOT NULL DEFAULT '',
                invoice_date DATE NOT NULL,
                due_date DATE NOT NULL,
                status VARCHAR(12) NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'paid')),
                currency CHAR(3) NOT NULL DEFAULT 'KES',
                subtotal NUMERIC(14, 2) NOT NULL DEFAULT 0,
                discount_amount NUMERIC(14, 2) NOT NULL DEFAULT 0,
                tax_rate NUMERIC(5, 2) NOT NULL DEFAULT 0,
                tax_amount NUMERIC(14, 2) NOT NULL DEFAULT 0,
                total NUMERIC(14, 2) NOT NULL DEFAULT 0,
                notes TEXT NOT NULL DEFAULT '',
                payment_instructions TEXT NOT NULL DEFAULT '',
                amount_paid NUMERIC(14, 2) NOT NULL DEFAULT 0,
                payment_date DATE,
                payment_reference VARCHAR(180) NOT NULL DEFAULT '',
                payment_note TEXT NOT NULL DEFAULT '',
                created_by VARCHAR(120) NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                pdf_content BYTEA NOT NULL DEFAULT decode('', 'hex')
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS invoice_items (
                id BIGSERIAL PRIMARY KEY,
                invoice_id BIGINT NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
                position INTEGER NOT NULL,
                product_slug VARCHAR(180),
                name VARCHAR(240) NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                quantity NUMERIC(12, 3) NOT NULL CHECK (quantity > 0),
                unit_price NUMERIC(14, 2) NOT NULL CHECK (unit_price >= 0),
                line_total NUMERIC(14, 2) NOT NULL CHECK (line_total >= 0),
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS invoices_status_date_idx ON invoices (status, invoice_date DESC, id DESC)')
        conn.execute('CREATE INDEX IF NOT EXISTS invoices_quote_reference_idx ON invoices (quote_reference)')
        conn.execute('CREATE INDEX IF NOT EXISTS invoice_items_invoice_position_idx ON invoice_items (invoice_id, position)')


def save_quote(data, ip_address):
    reference = f"ALIPEN-{secrets.token_hex(3).upper()}"
    with database_connection() as conn:
        conn.execute('''
            INSERT INTO quote_requests
                (reference, name, facility, facility_type, county, phone, email,
                 requirements, items, ip_address)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
        ''', (
            reference, data['name'], data['facility'], data.get('facilityType', ''),
            data.get('county', ''), data['phone'], data['email'],
            data.get('requirements', ''), json.dumps(data.get('items', []), ensure_ascii=False),
            ip_address,
        ))
    return reference


def admin_auth_configured():
    return bool(
        _password_hasher is not None
        and ADMIN_USERNAME
        and ADMIN_PASSWORD_HASH.startswith('$argon2id$')
    )


def verify_admin_credentials(username, password):
    if not admin_auth_configured() or not isinstance(username, str) or not isinstance(password, str):
        return False
    try:
        password_valid = _password_hasher.verify(ADMIN_PASSWORD_HASH, password)
    except (InvalidHashError, VerificationError, TypeError, ValueError):
        return False
    return password_valid and secrets.compare_digest(username, ADMIN_USERNAME)


def validate_admin_username(username):
    if not isinstance(username, str):
        return None
    username = username.strip()
    if not ADMIN_USERNAME_RE.fullmatch(username):
        return None
    return username


def password_hash_is_valid(password_hash):
    return isinstance(password_hash, str) and password_hash.startswith('$argon2id$')


def verify_password_hash(password_hash, password):
    if _password_hasher is None or not password_hash_is_valid(password_hash) or not isinstance(password, str):
        return False
    try:
        return _password_hasher.verify(password_hash, password)
    except (InvalidHashError, VerificationError, TypeError, ValueError):
        return False


def authenticate_admin(username, password):
    """Authenticate the legacy environment-backed primary or an active database admin."""
    if not isinstance(username, str) or not isinstance(password, str) or len(username) > 120 or len(password) > 1024:
        return None
    if verify_admin_credentials(username, password):
        return {'id': None, 'username': ADMIN_USERNAME, 'is_primary': True}
    if ADMIN_USERNAME and username.casefold() == ADMIN_USERNAME.casefold():
        return None
    if not username or _password_hasher is None:
        return None
    user = get_admin_user_for_authentication(username)
    if not user or not user[3] or not verify_password_hash(user[2], password):
        return None
    return {'id': user[0], 'username': user[1], 'is_primary': False, 'updated_at': user[4]}


class DuplicateAdminUsername(Exception):
    pass


def _admin_db_unique_violation(error):
    return getattr(error, 'sqlstate', None) == '23505'


def get_admin_user_for_authentication(username):
    with database_connection() as conn:
        return conn.execute('''
            SELECT id, username, password_hash, is_active, updated_at
            FROM admin_users WHERE LOWER(username) = LOWER(%s) LIMIT 1
        ''', (username,)).fetchone()


def list_admin_users():
    with database_connection() as conn:
        rows = conn.execute('''
            SELECT id, username, is_active, created_at
            FROM admin_users ORDER BY LOWER(username), id
        ''').fetchall()
    return [
        {'id': row[0], 'username': row[1], 'is_active': row[2],
         'created_at': row[3].isoformat() if hasattr(row[3], 'isoformat') else row[3]}
        for row in rows
    ]


def create_admin_user(username, password_hash):
    try:
        with database_connection() as conn:
            row = conn.execute('''
                INSERT INTO admin_users (username, password_hash)
                VALUES (%s, %s)
                RETURNING id, username, is_active, created_at
            ''', (username, password_hash)).fetchone()
    except Exception as error:
        if _admin_db_unique_violation(error):
            raise DuplicateAdminUsername from error
        raise
    return {'id': row[0], 'username': row[1], 'is_active': row[2],
            'created_at': row[3].isoformat() if hasattr(row[3], 'isoformat') else row[3]}


def update_admin_user(user_id, username=None, password_hash=None, is_active=None):
    assignments = []
    params = []
    if username is not None:
        assignments.append('username = %s')
        params.append(username)
    if password_hash is not None:
        assignments.append('password_hash = %s')
        params.append(password_hash)
    if is_active is not None:
        assignments.append('is_active = %s')
        params.append(is_active)
    if not assignments:
        return None
    assignments.append('updated_at = CURRENT_TIMESTAMP')
    params.append(user_id)
    try:
        with database_connection() as conn:
            row = conn.execute(f'''
                UPDATE admin_users SET {', '.join(assignments)}
                WHERE id = %s
                RETURNING id, username, is_active, created_at
            ''', tuple(params)).fetchone()
    except Exception as error:
        if _admin_db_unique_violation(error):
            raise DuplicateAdminUsername from error
        raise
    return ({'id': row[0], 'username': row[1], 'is_active': row[2],
             'created_at': row[3].isoformat() if hasattr(row[3], 'isoformat') else row[3]}
            if row else None)


def get_admin_user_session_state(user_id):
    with database_connection() as conn:
        return conn.execute('''
            SELECT is_active, updated_at FROM admin_users WHERE id = %s LIMIT 1
        ''', (user_id,)).fetchone()


def _session_key(session_token):
    return sha256(session_token.encode('utf-8')).hexdigest()


def create_admin_session(account):
    now = time.time()
    session_token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    with _admin_sessions_lock:
        expired = [key for key, item in _admin_sessions.items() if item['expires_at'] <= now]
        for key in expired:
            _admin_sessions.pop(key, None)
        _admin_sessions[_session_key(session_token)] = {
            'username': account['username'],
            'account_id': account.get('id'),
            'is_primary': bool(account.get('is_primary')),
            'account_updated_at': account.get('updated_at'),
            'csrf_token': csrf_token,
            'expires_at': now + ADMIN_SESSION_SECONDS,
        }
    return session_token, csrf_token


def revoke_admin_sessions(account_id):
    if account_id is None:
        return
    with _admin_sessions_lock:
        expired = [key for key, session in _admin_sessions.items() if session.get('account_id') == account_id]
        for key in expired:
            _admin_sessions.pop(key, None)


def get_admin_session(handler):
    try:
        cookie = SimpleCookie(handler.headers.get('Cookie', ''))
        morsel = cookie.get('alipen_admin_session')
        session_token = morsel.value if morsel else ''
    except CookieError:
        return None
    if not session_token:
        return None
    key = _session_key(session_token)
    now = time.time()
    with _admin_sessions_lock:
        session = _admin_sessions.get(key)
        if not session:
            return None
        if session['expires_at'] <= now:
            _admin_sessions.pop(key, None)
            return None
        session['expires_at'] = now + ADMIN_SESSION_SECONDS
        session = dict(session)
    if session.get('account_id') is not None:
        try:
            account_state = get_admin_user_session_state(session['account_id'])
        except Exception:
            return None
        if (not account_state or not account_state[0]
                or account_state[1] != session.get('account_updated_at')):
            with _admin_sessions_lock:
                _admin_sessions.pop(key, None)
            return None
    return session


def delete_admin_session(handler):
    try:
        cookie = SimpleCookie(handler.headers.get('Cookie', ''))
        morsel = cookie.get('alipen_admin_session')
        session_token = morsel.value if morsel else ''
    except CookieError:
        return
    if session_token:
        with _admin_sessions_lock:
            _admin_sessions.pop(_session_key(session_token), None)


def is_admin_login_limited(ip_address, now=None):
    now = now if now is not None else time.monotonic()
    cutoff = now - RATE_LIMIT_WINDOW_SECONDS
    with _admin_login_lock:
        attempts = _admin_login_attempts[ip_address]
        while attempts and attempts[0] <= cutoff:
            attempts.popleft()
        if len(attempts) >= ADMIN_LOGIN_LIMIT:
            return True
        attempts.append(now)
        return False


def clear_admin_login_attempts(ip_address):
    with _admin_login_lock:
        _admin_login_attempts.pop(ip_address, None)


def serialize_admin_quote(row):
    quote = dict(zip(ADMIN_QUOTE_COLUMNS, row))
    items = quote.get('items')
    if isinstance(items, str):
        try:
            items = json.loads(items)
        except json.JSONDecodeError:
            items = []
    quote['items'] = items if isinstance(items, list) else []
    created_at = quote.get('created_at')
    quote['created_at'] = created_at.isoformat() if hasattr(created_at, 'isoformat') else created_at
    follow_up_date = quote.get('follow_up_date')
    quote['follow_up_date'] = follow_up_date.isoformat() if hasattr(follow_up_date, 'isoformat') else follow_up_date
    quote['status'] = quote.get('status') or 'received'
    return quote


def get_admin_overview():
    today = datetime.now(BUSINESS_TIMEZONE).date()
    with database_connection() as conn:
        row = conn.execute('''
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE status IS NULL OR status IN ('', 'new', 'received')) AS new,
                COUNT(*) FILTER (WHERE status = 'in_progress') AS in_progress,
                COUNT(*) FILTER (WHERE status = 'completed') AS completed,
                COUNT(*) FILTER (WHERE status = 'won') AS won,
                COUNT(*) FILTER (WHERE follow_up_date <= %s AND follow_up_completed = FALSE) AS follow_up_due
            FROM quote_requests
        ''', (today,)).fetchone()
        recent_rows = conn.execute(f'''
            SELECT {', '.join(ADMIN_QUOTE_COLUMNS)}
            FROM quote_requests
            ORDER BY created_at DESC NULLS LAST, id DESC
            LIMIT %s
        ''', (5,)).fetchall()
        attention_rows = conn.execute(f'''
            SELECT {', '.join(ADMIN_QUOTE_COLUMNS)}
            FROM quote_requests
            WHERE (status IS NULL OR status IN ('', 'new', 'received', 'in_progress'))
               OR (follow_up_date <= %s AND follow_up_completed = FALSE)
            ORDER BY CASE
                         WHEN follow_up_date <= %s AND follow_up_completed = FALSE THEN 0
                         WHEN status IS NULL OR status IN ('', 'new', 'received') THEN 1
                         ELSE 2
                     END,
                     follow_up_date ASC NULLS LAST, created_at DESC NULLS LAST, id DESC
            LIMIT %s
        ''', (today, today, 5)).fetchall()
        follow_up_rows = conn.execute(f'''
            SELECT {', '.join(ADMIN_QUOTE_COLUMNS)}
            FROM quote_requests
            WHERE follow_up_date IS NOT NULL AND follow_up_completed = FALSE
            ORDER BY follow_up_date ASC, created_at DESC NULLS LAST, id DESC
            LIMIT %s
        ''', (8,)).fetchall()
    return {
        'total': row[0],
        'new': row[1],
        'in_progress': row[2],
        'completed': row[3],
        'won': row[4],
        'follow_up_due': row[5],
        'recent': [serialize_admin_quote(item) for item in recent_rows],
        'attention': [serialize_admin_quote(item) for item in attention_rows],
        'follow_ups': [serialize_admin_quote(item) for item in follow_up_rows],
    }


def list_admin_quotes(search='', status='all', page=1, page_size=20, date_from=None, date_to=None, follow_up='all'):
    clauses = []
    params = []
    if search:
        pattern = f'%{search}%'
        clauses.append('(reference ILIKE %s OR name ILIKE %s OR facility ILIKE %s OR email ILIKE %s)')
        params.extend((pattern, pattern, pattern, pattern))
    if status == 'new':
        clauses.append("(status IS NULL OR status IN ('', 'new', 'received'))")
    elif status in ('in_progress', 'completed'):
        clauses.append('status = %s')
        params.append(status)
    elif status in ('won', 'lost'):
        clauses.append('status = %s')
        params.append(status)
    if date_from:
        clauses.append('created_at >= %s')
        params.append(datetime.combine(date_from, datetime.min.time(), BUSINESS_TIMEZONE))
    if date_to:
        clauses.append('created_at < %s')
        params.append(datetime.combine(date_to + timedelta(days=1), datetime.min.time(), BUSINESS_TIMEZONE))
    if follow_up == 'due':
        clauses.append('follow_up_date <= %s AND follow_up_completed = FALSE')
        params.append(datetime.now(BUSINESS_TIMEZONE).date())

    where_sql = f" WHERE {' AND '.join(clauses)}" if clauses else ''
    offset = (page - 1) * page_size
    with database_connection() as conn:
        total = conn.execute(f'SELECT COUNT(*) FROM quote_requests{where_sql}', tuple(params)).fetchone()[0]
        rows = conn.execute(f'''
            SELECT {', '.join(ADMIN_QUOTE_COLUMNS)}
            FROM quote_requests{where_sql}
            ORDER BY created_at DESC NULLS LAST, id DESC
            LIMIT %s OFFSET %s
        ''', tuple(params + [page_size, offset])).fetchall()
    return {'items': [serialize_admin_quote(row) for row in rows], 'total': total, 'page': page, 'pageSize': page_size}


def get_admin_quote(reference):
    with database_connection() as conn:
        row = conn.execute(f'''
            SELECT {', '.join(ADMIN_QUOTE_COLUMNS)}
            FROM quote_requests WHERE reference = %s LIMIT 1
        ''', (reference,)).fetchone()
    return serialize_admin_quote(row) if row else None


class InvoiceValidationError(ValueError):
    pass


class InvoiceNotFound(LookupError):
    pass


class InvoiceAlreadyPaid(ValueError):
    pass


class InvoicePaidFinancialChange(ValueError):
    pass


def _invoice_decimal(value, field, scale=2, maximum=Decimal('999999999999.99')):
    if isinstance(value, bool):
        raise InvoiceValidationError(f'{field} must be a valid non-negative amount.')
    if value in (None, ''):
        value = '0'
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number < 0 or number > maximum:
            raise InvalidOperation
        return number.quantize(Decimal('1').scaleb(-scale), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        raise InvoiceValidationError(f'{field} must be a valid non-negative amount.')


def _invoice_date(value, field, default=None):
    if value in (None, ''):
        return default
    try:
        parsed = date.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        parsed = None
    if parsed is None or parsed.year < 2000 or parsed.year > 2200:
        raise InvoiceValidationError(f'{field} must be a valid date.')
    return parsed


def validate_invoice_payload(data):
    if not isinstance(data, dict):
        raise InvoiceValidationError('Provide invoice details.')
    today = datetime.now(BUSINESS_TIMEZONE).date()
    invoice_date = _invoice_date(data.get('invoice_date'), 'Invoice date', today)
    due_date = _invoice_date(data.get('due_date'), 'Due date', invoice_date)
    if due_date < invoice_date:
        raise InvoiceValidationError('Due date cannot be before the invoice date.')
    name = clean_text(data.get('customer_name'), 180)
    email = clean_text(data.get('customer_email'), 180)
    company = clean_text(data.get('company_name'), 180)
    address = clean_text(data.get('customer_address'), 1000)
    if not name:
        raise InvoiceValidationError('Customer name is required.')
    if email and (not EMAIL_RE.fullmatch(email) or parseaddr(email)[1] != email):
        raise InvoiceValidationError('Enter a valid customer email address.')
    currency = clean_text(data.get('currency') or 'KES', 3).upper()
    if not re.fullmatch(r'[A-Z]{3}', currency):
        raise InvoiceValidationError('Currency must be a three-letter code.')

    items = data.get('items')
    if not isinstance(items, list) or not items or len(items) > 100:
        raise InvoiceValidationError('Add between 1 and 100 invoice items.')
    catalogue_slugs = invoice_catalogue_product_slugs()
    normalized_items = []
    subtotal = Decimal('0.00')
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise InvoiceValidationError(f'Invoice item {index} is invalid.')
        name_value = clean_text(item.get('name'), 240)
        description = clean_text(item.get('description'), 1000)
        if not name_value:
            raise InvoiceValidationError(f'Invoice item {index} needs a name.')
        slug = clean_text(item.get('product_slug'), 180) or None
        if slug and slug not in catalogue_slugs:
            raise InvoiceValidationError(f'Invoice item {index} refers to an unknown catalogue product.')
        if 'unit_price' not in item or item.get('unit_price') in (None, ''):
            raise InvoiceValidationError(f'Enter a unit price for item {index}.')
        quantity = _invoice_decimal(item.get('quantity', 1), f'Quantity for item {index}', 3, Decimal('999999.999'))
        if quantity <= 0:
            raise InvoiceValidationError(f'Quantity for item {index} must be greater than zero.')
        unit_price = _invoice_decimal(item.get('unit_price'), f'Unit price for item {index}')
        line_total = (quantity * unit_price).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        subtotal += line_total
        if line_total > Decimal('999999999999.99') or subtotal > Decimal('999999999999.99'):
            raise InvoiceValidationError('Invoice amounts exceed the supported maximum.')
        normalized_items.append({
            'product_slug': slug, 'name': name_value, 'description': description,
            'quantity': quantity, 'unit_price': unit_price, 'line_total': line_total,
        })
    subtotal = subtotal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    discount = _invoice_decimal(data.get('discount_amount'), 'Discount')
    if discount > subtotal:
        raise InvoiceValidationError('Discount cannot exceed the subtotal.')
    tax_rate = _invoice_decimal(data.get('tax_rate'), 'Tax rate', 2, Decimal('100.00'))
    tax_amount = ((subtotal - discount) * tax_rate / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    total = subtotal - discount + tax_amount
    if total > Decimal('999999999999.99'):
        raise InvoiceValidationError('Invoice total exceeds the supported maximum.')
    quote_reference = clean_text(data.get('quote_reference'), 20) or None
    if quote_reference and not re.fullmatch(r'ALIPEN-[A-Za-z0-9]{6}', quote_reference):
        raise InvoiceValidationError('Quote reference is invalid.')
    return {
        'quote_reference': quote_reference, 'customer_name': name, 'customer_email': email,
        'company_name': company, 'customer_address': address, 'invoice_date': invoice_date,
        'due_date': due_date, 'currency': currency, 'subtotal': subtotal,
        'discount_amount': discount, 'tax_rate': tax_rate, 'tax_amount': tax_amount,
        'total': total, 'notes': clean_text(data.get('notes'), 5000),
        'payment_instructions': clean_text(data.get('payment_instructions'), 2000),
        'items': normalized_items,
    }


def invoice_catalogue_product_slugs():
    global _catalogue_product_slugs
    if _catalogue_product_slugs is None:
        source = (DIRECTORY / 'products.js').read_text(encoding='utf-8')
        _catalogue_product_slugs = set(re.findall(r"\bslug:\s*'([a-z0-9-]+)'", source))
    return _catalogue_product_slugs


def _iso(value):
    return value.isoformat() if hasattr(value, 'isoformat') else value


def _decimal_text(value):
    return format(Decimal(str(value or 0)).quantize(Decimal('0.01')), '.2f')


def serialize_invoice(row, items=None):
    invoice = dict(zip(INVOICE_COLUMNS, row)) if not isinstance(row, dict) else dict(row)
    for field in ('invoice_date', 'due_date', 'payment_date', 'created_at', 'updated_at'):
        invoice[field] = _iso(invoice.get(field))
    for field in ('subtotal', 'discount_amount', 'tax_rate', 'tax_amount', 'total', 'amount_paid'):
        invoice[field] = _decimal_text(invoice.get(field))
    invoice['items'] = [serialize_invoice_item(item) for item in (items or invoice.get('items') or [])]
    invoice.pop('pdf_content', None)
    return invoice


def serialize_invoice_item(row):
    item = dict(zip(INVOICE_ITEM_COLUMNS, row)) if not isinstance(row, dict) else dict(row)
    for field in ('quantity', 'unit_price', 'line_total'):
        places = 3 if field == 'quantity' else 2
        item[field] = format(Decimal(str(item.get(field) or 0)).quantize(Decimal('1').scaleb(-places)), f'.{places}f')
    return item


def _insert_invoice_items(conn, invoice_id, items):
    for position, item in enumerate(items, start=1):
        conn.execute('''
            INSERT INTO invoice_items
                (invoice_id, position, product_slug, name, description, quantity, unit_price, line_total)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', (invoice_id, position, item['product_slug'], item['name'], item['description'],
              item['quantity'], item['unit_price'], item['line_total']))


def _invoice_pdf_data(invoice, items):
    data = dict(invoice)
    data['items'] = items
    return data


def create_invoice(data, username):
    invoice = validate_invoice_payload(data)
    with database_connection() as conn:
        if invoice['quote_reference']:
            quote = conn.execute('SELECT reference FROM quote_requests WHERE reference = %s', (invoice['quote_reference'],)).fetchone()
            if not quote:
                raise InvoiceNotFound('The selected quote could not be found.')
        sequence = conn.execute(f"SELECT nextval('{INVOICE_NUMBER_SEQUENCE}')").fetchone()[0]
        invoice_number = f"ALP-{invoice['invoice_date'].year}-{int(sequence):06d}"
        params = tuple(invoice[field] for field in (
            'quote_reference', 'customer_name', 'customer_email', 'company_name', 'customer_address',
            'invoice_date', 'due_date', 'currency', 'subtotal', 'discount_amount', 'tax_rate',
            'tax_amount', 'total', 'notes', 'payment_instructions'))
        row = conn.execute(f'''
            INSERT INTO invoices
                (invoice_number, quote_reference, customer_name, customer_email, company_name,
                 customer_address, invoice_date, due_date, currency, subtotal, discount_amount,
                 tax_rate, tax_amount, total, notes, payment_instructions, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING {', '.join(INVOICE_COLUMNS)}
        ''', (invoice_number, *params, clean_text(username, 120))).fetchone()
        invoice_id = row[0]
        _insert_invoice_items(conn, invoice_id, invoice['items'])
        invoice['id'] = invoice_id
        invoice['invoice_number'] = invoice_number
        invoice['status'] = 'new'
        invoice['amount_paid'] = Decimal('0.00')
        invoice['payment_date'] = None
        invoice['payment_reference'] = ''
        invoice['payment_note'] = ''
        invoice['created_by'] = clean_text(username, 120)
        invoice['created_at'] = datetime.now(timezone.utc)
        invoice['updated_at'] = invoice['created_at']
        pdf_content = invoice_pdf(_invoice_pdf_data(invoice, invoice['items']))
        conn.execute('UPDATE invoices SET pdf_content = %s WHERE id = %s', (pdf_content, invoice_id))
    return serialize_invoice(invoice)


def list_invoices(search='', status='new', page=1, page_size=20):
    clauses, params = [], []
    if status in ('new', 'paid'):
        clauses.append('status = %s')
        params.append(status)
    if search:
        clauses.append("(invoice_number ILIKE %s OR customer_name ILIKE %s OR company_name ILIKE %s OR customer_email ILIKE %s)")
        pattern = f'%{search}%'
        params.extend((pattern, pattern, pattern, pattern))
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ''
    offset = (page - 1) * page_size
    with database_connection() as conn:
        total = conn.execute(f'SELECT COUNT(*) FROM invoices{where}', tuple(params)).fetchone()[0]
        rows = conn.execute(f'''
            SELECT {', '.join(INVOICE_COLUMNS)} FROM invoices{where}
            ORDER BY invoice_date DESC, id DESC LIMIT %s OFFSET %s
        ''', tuple(params + [page_size, offset])).fetchall()
    return {'items': [serialize_invoice(row) for row in rows], 'total': total, 'page': page, 'pageSize': page_size}


def get_invoice(invoice_id, include_pdf=False, lock=False):
    with database_connection() as conn:
        row = conn.execute(f'SELECT {INVOICE_COLUMN_SQL} FROM invoices WHERE id = %s' + (' FOR UPDATE' if lock else ''), (invoice_id,)).fetchone()
        if not row:
            return None if not include_pdf else (None, None)
        items = conn.execute(f'SELECT {INVOICE_ITEM_COLUMN_SQL} FROM invoice_items WHERE invoice_id = %s ORDER BY position, id', (invoice_id,)).fetchall()
        pdf_content = None
        if include_pdf:
            pdf_content = conn.execute('SELECT pdf_content FROM invoices WHERE id = %s', (invoice_id,)).fetchone()[0]
    return (serialize_invoice(row, items), pdf_content) if include_pdf else serialize_invoice(row, items)


def _item_financial_snapshot(items):
    return [(
        item.get('product_slug'), item.get('name'), item.get('description'),
        Decimal(str(item.get('quantity'))).quantize(Decimal('0.001')),
        Decimal(str(item.get('unit_price'))).quantize(Decimal('0.01')),
        Decimal(str(item.get('line_total'))).quantize(Decimal('0.01')),
    ) for item in items]


def update_invoice(invoice_id, data):
    invoice = validate_invoice_payload(data)
    with database_connection() as conn:
        row = conn.execute(f'SELECT {INVOICE_COLUMN_SQL} FROM invoices WHERE id = %s FOR UPDATE', (invoice_id,)).fetchone()
        if not row:
            raise InvoiceNotFound('Invoice not found.')
        current = dict(zip(INVOICE_COLUMNS, row))
        current_items_rows = conn.execute(f'SELECT {INVOICE_ITEM_COLUMN_SQL} FROM invoice_items WHERE invoice_id = %s ORDER BY position, id', (invoice_id,)).fetchall()
        current_items = [serialize_invoice_item(item) for item in current_items_rows]
        if current['status'] == 'paid':
            paid_fields_match = all(
                Decimal(str(current[field])).quantize(Decimal('0.01')) == invoice[field]
                for field in ('subtotal', 'discount_amount', 'tax_rate', 'tax_amount', 'total')
            ) and current['currency'] == invoice['currency']
            if not paid_fields_match or _item_financial_snapshot(current_items) != _item_financial_snapshot(invoice['items']):
                raise InvoicePaidFinancialChange('Paid invoice amounts and line items are locked. Create a separate invoice for a financial correction.')
        updated_row = conn.execute(f'''
            UPDATE invoices SET customer_name = %s, customer_email = %s, company_name = %s,
                customer_address = %s, invoice_date = %s, due_date = %s, currency = %s,
                subtotal = %s, discount_amount = %s, tax_rate = %s, tax_amount = %s,
                total = %s, notes = %s, payment_instructions = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s RETURNING {', '.join(INVOICE_COLUMNS)}
        ''', (invoice['customer_name'], invoice['customer_email'], invoice['company_name'],
              invoice['customer_address'], invoice['invoice_date'], invoice['due_date'], invoice['currency'],
              invoice['subtotal'], invoice['discount_amount'], invoice['tax_rate'], invoice['tax_amount'],
              invoice['total'], invoice['notes'], invoice['payment_instructions'], invoice_id)).fetchone()
        if current['status'] != 'paid':
            conn.execute('DELETE FROM invoice_items WHERE invoice_id = %s', (invoice_id,))
            _insert_invoice_items(conn, invoice_id, invoice['items'])
            pdf_items = invoice['items']
        else:
            pdf_items = current_items
        updated = dict(zip(INVOICE_COLUMNS, updated_row))
        serialized = serialize_invoice(updated, pdf_items)
        pdf_content = invoice_pdf(serialized)
        conn.execute('UPDATE invoices SET pdf_content = %s WHERE id = %s', (pdf_content, invoice_id))
    return serialize_invoice(updated, pdf_items)


def mark_invoice_paid(invoice_id, payment_reference='', payment_note='', payment_date=None):
    paid_date = _invoice_date(payment_date, 'Payment date', datetime.now(BUSINESS_TIMEZONE).date())
    reference = clean_text(payment_reference, 180)
    note = clean_text(payment_note, 2000)
    with database_connection() as conn:
        row = conn.execute(f'SELECT {INVOICE_COLUMN_SQL} FROM invoices WHERE id = %s FOR UPDATE', (invoice_id,)).fetchone()
        if not row:
            raise InvoiceNotFound('Invoice not found.')
        current = dict(zip(INVOICE_COLUMNS, row))
        if current['status'] == 'paid':
            raise InvoiceAlreadyPaid('This invoice has already been marked as paid.')
        updated_row = conn.execute(f'''
            UPDATE invoices SET status = 'paid', amount_paid = total, payment_date = %s,
                payment_reference = %s, payment_note = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s RETURNING {', '.join(INVOICE_COLUMNS)}
        ''', (paid_date, reference, note, invoice_id)).fetchone()
        items = [serialize_invoice_item(item) for item in conn.execute(
            f'SELECT {INVOICE_ITEM_COLUMN_SQL} FROM invoice_items WHERE invoice_id = %s ORDER BY position, id',
            (invoice_id,)).fetchall()]
        updated = dict(zip(INVOICE_COLUMNS, updated_row))
        pdf_content = invoice_pdf(serialize_invoice(updated, items))
        conn.execute('UPDATE invoices SET pdf_content = %s WHERE id = %s', (pdf_content, invoice_id))
    return serialize_invoice(updated, items)


def list_quote_notes(reference):
    with database_connection() as conn:
        rows = conn.execute('''
            SELECT id, author_username, content, created_at, updated_at
            FROM quote_notes WHERE quote_reference = %s ORDER BY created_at ASC, id ASC
        ''', (reference,)).fetchall()
    return [dict(id=row[0], author=row[1], content=row[2],
                 created_at=row[3].isoformat() if hasattr(row[3], 'isoformat') else row[3],
                 updated_at=row[4].isoformat() if hasattr(row[4], 'isoformat') else row[4]) for row in rows]


def create_quote_note(reference, author, content):
    with database_connection() as conn:
        row = conn.execute('''
            INSERT INTO quote_notes (quote_reference, author_username, content)
            SELECT reference, %s, %s FROM quote_requests WHERE reference = %s
            RETURNING id, author_username, content, created_at, updated_at
        ''', (author, content, reference)).fetchone()
    return dict(id=row[0], author=row[1], content=row[2],
                created_at=row[3].isoformat() if hasattr(row[3], 'isoformat') else row[3],
                updated_at=row[4].isoformat() if hasattr(row[4], 'isoformat') else row[4]) if row else None


def update_quote_note(note_id, content):
    with database_connection() as conn:
        row = conn.execute('''
            UPDATE quote_notes SET content = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s RETURNING id, author_username, content, created_at, updated_at
        ''', (content, note_id)).fetchone()
    return dict(id=row[0], author=row[1], content=row[2],
                created_at=row[3].isoformat() if hasattr(row[3], 'isoformat') else row[3],
                updated_at=row[4].isoformat() if hasattr(row[4], 'isoformat') else row[4]) if row else None


def get_quote_note(note_id):
    with database_connection() as conn:
        row = conn.execute('''
            SELECT id, author_username, content, created_at, updated_at
            FROM quote_notes WHERE id = %s
        ''', (note_id,)).fetchone()
    return dict(id=row[0], author=row[1], content=row[2],
                created_at=row[3].isoformat() if hasattr(row[3], 'isoformat') else row[3],
                updated_at=row[4].isoformat() if hasattr(row[4], 'isoformat') else row[4]) if row else None


def delete_quote_note(note_id):
    with database_connection() as conn:
        row = conn.execute('DELETE FROM quote_notes WHERE id = %s RETURNING id', (note_id,)).fetchone()
    return bool(row)


def update_follow_up(reference, follow_up_date, note=None, completed=None):
    with database_connection() as conn:
        row = conn.execute('''
            UPDATE quote_requests
            SET follow_up_date = COALESCE(%s, follow_up_date), follow_up_note = COALESCE(%s, follow_up_note),
                follow_up_completed = COALESCE(%s, follow_up_completed)
            WHERE reference = %s
            RETURNING reference, follow_up_date, follow_up_note, follow_up_completed
        ''', (follow_up_date, note, completed, reference)).fetchone()
    return dict(reference=row[0], date=row[1].isoformat() if hasattr(row[1], 'isoformat') else row[1],
                note=row[2], completed=row[3]) if row else None


def valid_admin_note(value):
    if not isinstance(value, str):
        return None
    content = value.strip()
    if not content or len(content) > 5000:
        return None
    return content


def update_admin_quote_status(reference, status):
    with database_connection() as conn:
        row = conn.execute('''
            UPDATE quote_requests
            SET status = %s
            WHERE reference = %s
            RETURNING reference, status
        ''', (status, reference)).fetchone()
    return {'reference': row[0], 'status': row[1]} if row else None


def escape(value):
    return html.escape(str(value or ''), quote=True).strip()


def format_items(items):
    """Render requested products as a compact HTML table and text list."""
    rows = items or [{'name': 'General catalogue and procurement inquiry', 'quantity': 1}]
    html_rows, text_rows = [], []
    for item in rows:
        name = escape(item.get('name') or 'Medical product')
        raw_description = item.get('description') or item.get('specifications') or item.get('category')
        description = escape(raw_description) or '&mdash;'
        quantity = escape(item.get('quantity', 1))
        values = (f'<strong>{name}</strong>', description, quantity)
        aligns = ('left', 'left', 'center')
        html_rows.append('<tr>' + ''.join(f'<td align="{align}" style="padding:11px 8px;border-bottom:1px solid #e2e8f0;vertical-align:top;overflow-wrap:anywhere;word-break:normal">{value}</td>' for align, value in zip(aligns, values)) + '</tr>')
        text_row = f'- {item.get("name") or "Medical product"}'
        if raw_description:
            text_row += f' — {raw_description}'
        text_row += f' | Quantity: {item.get("quantity", 1)}'
        text_rows.append(text_row)
    headers = (('Item', 'left'), ('Description / Specifications', 'left'), ('Quantity', 'center'))
    head = '<tr style="background:#edf4fb">' + ''.join(f'<th align="{align}" style="padding:9px;border-bottom:1px solid #cbd5e1;color:#0d3c78">{label}</th>' for label, align in headers) + '</tr>'
    table = ('<table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="width:100%;table-layout:fixed;border-collapse:collapse;margin:10px 0;font-size:12px;line-height:18px">' + f'<thead>{head}</thead><tbody>{"".join(html_rows)}</tbody></table>')
    return table, '\n'.join(text_rows)


def email_logo_url():
    """Build the logo URL from Render's assigned public URL or a configured public site URL."""
    for candidate in (RENDER_EXTERNAL_URL, SITE_URL):
        parsed = urllib.parse.urlparse(candidate)
        if parsed.scheme == 'https' and parsed.hostname not in (None, 'localhost', '127.0.0.1', '0.0.0.0'):
            return f'{candidate}/public/images/logo.png'
    return 'https://alipen-website.onrender.com/public/images/logo.png'


def email_layout(title, body):
    logo_url = escape(email_logo_url())
    website_url = escape(email_logo_url().rsplit('/public/', 1)[0])
    return f'''<!doctype html><html><body style="margin:0;padding:0;background:#f4f7fb;font-family:Arial,Helvetica,sans-serif;color:#1e293b">
    <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="width:100%;background:#f4f7fb"><tr><td align="center" style="padding:24px 12px">
      <table role="presentation" cellpadding="0" cellspacing="0" width="680" style="width:100%;max-width:680px;background:#ffffff;border:1px solid #e2e8f0;border-collapse:separate;border-spacing:0">
        <tr><td align="center" style="padding:20px 24px 16px;border-bottom:1px solid #e2e8f0"><img src="{logo_url}" width="220" alt="Alipen Solutions Agency Ltd" style="display:block;width:220px;max-width:100%;height:auto;border:0" /><div style="padding-top:8px;font-size:12px;letter-spacing:1px;color:#64748b">ALIPEN SOLUTIONS AGENCY LTD</div></td></tr>
        <tr><td style="padding:26px 24px"><h1 style="margin:0 0 16px;font-size:24px;line-height:30px;color:#0d3c78">{escape(title)}</h1>{body}</td></tr>
        <tr><td style="padding:18px 24px;background:#0d3c78;color:#e2e8f0;font-size:13px;line-height:21px">Alipen Solutions Agency Ltd<br /><a href="tel:+254712272463" style="color:#ffffff;text-decoration:none">+254 712 272 463</a> &nbsp;|&nbsp; <a href="mailto:info@alipen.co.ke" style="color:#ffffff;text-decoration:none">info@alipen.co.ke</a><br />Nairobi, Kenya &nbsp;|&nbsp; <a href="{website_url}" style="color:#ffffff;text-decoration:underline">Visit our website</a></td></tr>
      </table></td></tr></table></body></html>'''


def _resend_error_code(response_body):
    """Extract only a safe provider error identifier, never log response PII."""
    try:
        payload = json.loads(response_body.decode('utf-8', errors='replace'))
    except (AttributeError, UnicodeDecodeError, json.JSONDecodeError):
        return 'unparseable_error'
    if isinstance(payload, dict):
        code = payload.get('name') or payload.get('code')
        if isinstance(code, str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,80}', code):
            return code
    return 'api_error'


def _log_resend_failure(notification_type, reference, status_code, error_code):
    logger.warning(
        'Resend email delivery failed notification=%s reference=%s http_status=%s error_code=%s',
        notification_type, reference or 'unknown', status_code or 'unavailable', error_code,
    )


def resend_email(to_address, subject, html_body, text_body, notification_type='email', reference=''):
    if not RESEND_API_KEY or not MAIL_FROM:
        missing = []
        if not RESEND_API_KEY:
            missing.append('RESEND_API_KEY')
        if not MAIL_FROM:
            missing.append('MAIL_FROM')
        logger.warning(
            'Resend email delivery not configured notification=%s reference=%s missing=%s',
            notification_type, reference or 'unknown', ','.join(missing),
        )
        return 'not_configured'
    payload = json.dumps({
        'from': MAIL_FROM,
        'to': [to_address],
        'subject': subject,
        'html': html_body,
        'text': text_body,
    }).encode('utf-8')
    request = urllib.request.Request(
        'https://api.resend.com/emails',
        data=payload,
        headers={
            'Authorization': f'Bearer {RESEND_API_KEY}',
            'Content-Type': 'application/json',
            'User-Agent': 'Alipen-Website/1.0',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            if 200 <= response.status < 300:
                return 'accepted'
            error_body = response.read(8192)
            _log_resend_failure(notification_type, reference, response.status, _resend_error_code(error_body))
            return 'failed'
    except urllib.error.HTTPError as error:
        try:
            error_body = error.read(8192)
        except Exception:
            error_body = b''
        _log_resend_failure(notification_type, reference, error.code, _resend_error_code(error_body))
        return 'failed'
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
        _log_resend_failure(notification_type, reference, None, type(error).__name__)
        return 'failed'


def send_quote_emails(data, reference):
    items_html, items_text = format_items(data.get('items', []))
    submitted = datetime.now(timezone.utc).strftime('%d %B %Y, %H:%M UTC')
    ref_panel = (f'<div style="margin:0 0 18px;padding:13px 15px;background:#edf4fb;border-left:4px solid #0d3c78"><div style="font-size:11px;letter-spacing:.7px;color:#475569">QUOTE REFERENCE</div><div style="font-size:20px;font-weight:bold;line-height:28px;color:#0d3c78">{escape(reference)}</div></div>')
    customer_rows = (('Name', data.get('name')), ('Facility / company', data.get('facility')), ('Email', data.get('email')), ('Phone', data.get('phone')), ('Location', data.get('county')), ('Facility type', data.get('facilityType')))
    detail_rows = []
    for label, value in customer_rows:
        display = f'<a href="mailto:{escape(value)}" style="color:#0d3c78">{escape(value)}</a>' if label == 'Email' and value else escape(value) or 'Not provided'
        detail_rows.append(f'<tr><td style="width:150px;padding:6px 10px 6px 0;color:#64748b;vertical-align:top">{escape(label)}</td><td style="padding:6px 0;vertical-align:top;overflow-wrap:anywhere">{display}</td></tr>')
    details_html = '<table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse;font-size:14px;line-height:21px">' + ''.join(detail_rows) + '</table>'
    notes = data.get('requirements') or ''
    customer_html = email_layout('We’ve received your quote request', f'''<p style="margin:0 0 16px;font-size:15px;line-height:23px">Hello {escape(data.get('name'))}, thank you for requesting a quote from Alipen. Your request has been received, and our team will review it and follow up with you.</p>{ref_panel}<h2 style="margin:22px 0 10px;font-size:16px;color:#0d3c78">Requested items</h2>{items_html}<h2 style="margin:22px 0 10px;font-size:16px;color:#0d3c78">Your details</h2>{details_html}<h2 style="margin:22px 0 10px;font-size:16px;color:#0d3c78">Your notes</h2><div style="padding:12px;background:#f8fafc;border:1px solid #e2e8f0;font-size:14px;line-height:21px;white-space:pre-wrap">{escape(notes) or 'No additional notes provided.'}</div><p style="margin:20px 0 0;font-size:14px;line-height:22px">Please keep your quote reference for follow-up. Contact us at <a href="tel:+254712272463" style="color:#0d3c78">+254 712 272 463</a> or <a href="mailto:info@alipen.co.ke" style="color:#0d3c78">info@alipen.co.ke</a>.</p>''')
    customer_text = (f"Hello {data.get('name')}, thank you for requesting a quote from Alipen. Your request has been received and our team will review it.\n\nQUOTE REFERENCE: {reference}\nSubmitted: {submitted}\n\nRequested items:\n{items_text}\n\nFacility / company: {data.get('facility')}\nEmail: {data.get('email')}\nPhone: {data.get('phone') or 'Not provided'}\nLocation: {data.get('county') or 'Not provided'}\n\nAdditional notes: {notes or 'None'}\n\nAlipen Solutions Agency Ltd\n+254 712 272 463 | info@alipen.co.ke\nNairobi, Kenya")
    requirements_html = escape(notes) or 'No additional notes provided.'
    admin_html = email_layout('New Quote Request Received', f'''<p style="margin:0 0 16px;color:#475569;font-size:14px;line-height:22px">A customer has submitted a quote request. Review the details below.</p>{ref_panel}<div style="margin:0 0 8px;color:#64748b;font-size:13px">Submitted: {escape(submitted)}</div><h2 style="margin:22px 0 10px;font-size:16px;color:#0d3c78">Customer information</h2>{details_html}<h2 style="margin:22px 0 10px;font-size:16px;color:#0d3c78">Requested items</h2>{items_html}<h2 style="margin:22px 0 10px;font-size:16px;color:#0d3c78">Additional notes</h2><div style="padding:12px;background:#f8fafc;border:1px solid #e2e8f0;font-size:14px;line-height:21px;white-space:pre-wrap">{requirements_html}</div>''')
    admin_text = (f"NEW QUOTE REQUEST RECEIVED\nReference: {reference}\nSubmitted: {submitted}\n\nCustomer information\nName: {data.get('name')}\nFacility / company: {data.get('facility')}\nEmail: {data.get('email')}\nPhone: {data.get('phone') or 'Not provided'}\nLocation: {data.get('county') or 'Not provided'}\nFacility type: {data.get('facilityType') or 'Not provided'}\n\nRequested items:\n{items_text}\n\nAdditional notes: {notes or 'No additional notes provided.'}")
    if not RESEND_API_KEY or not MAIL_FROM:
        missing = []
        if not RESEND_API_KEY:
            missing.append('RESEND_API_KEY')
        if not MAIL_FROM:
            missing.append('MAIL_FROM')
        logger.error('Quote emails not sent reference=%s missing configuration=%s', reference, ','.join(missing))
        return {'admin': 'not_configured', 'customer': 'not_configured'}
    if ADMIN_EMAIL:
        admin_status = resend_email(ADMIN_EMAIL, f'New Alipen quote request — {reference}', admin_html, admin_text, notification_type='admin', reference=reference)
    else:
        logger.error('Admin quote notification not sent reference=%s missing configuration=ADMIN_EMAIL', reference)
        admin_status = 'not_configured'
    customer_status = resend_email(data['email'], f'Quote request received — {reference}', customer_html, customer_text, notification_type='customer', reference=reference)
    return {'admin': admin_status, 'customer': customer_status}


def client_ip(handler):
    forwarded = handler.headers.get('X-Forwarded-For', '').split(',')[0].strip()
    candidate = forwarded or handler.client_address[0]
    return candidate[:64]


def is_rate_limited(ip_address, now=None):
    now = now if now is not None else time.monotonic()
    cutoff = now - RATE_LIMIT_WINDOW_SECONDS
    with _rate_limit_lock:
        recent = _request_times[ip_address]
        while recent and recent[0] <= cutoff:
            recent.popleft()
        if len(recent) >= RATE_LIMIT_REQUESTS:
            return True
        recent.append(now)
        return False


def clean_text(value, limit):
    if not isinstance(value, str):
        return ''
    value = ''.join(char for char in value if char in '\t\n\r' or ord(char) >= 32)
    return ' '.join(value.strip().split())[:limit]


def validate_submission(data):
    if not isinstance(data, dict):
        return None, 'Please submit a valid quote request.'
    if data.get('website'):
        return None, 'Unable to process this submission.'

    cleaned = {
        'name': clean_text(data.get('name'), 120),
        'facility': clean_text(data.get('facility'), 180),
        'facilityType': clean_text(data.get('facilityType'), 100),
        'county': clean_text(data.get('county'), 100),
        'phone': clean_text(data.get('phone'), 50),
        'email': clean_text(data.get('email'), 180),
        'requirements': clean_text(data.get('requirements'), 3000),
    }
    if not all(cleaned[field] for field in ('name', 'facility', 'county', 'phone', 'email')):
        return None, 'Please complete all required fields.'
    if not EMAIL_RE.fullmatch(cleaned['email']) or parseaddr(cleaned['email'])[1] != cleaned['email']:
        return None, 'Please enter a valid email address.'
    if len(cleaned['phone']) < 7:
        return None, 'Please enter a valid phone number.'

    incoming_items = data.get('items', [])
    if not isinstance(incoming_items, list):
        return None, 'Please submit a valid product list.'
    cleaned_items = []
    for item in incoming_items[:50]:
        if not isinstance(item, dict):
            continue
        name = clean_text(item.get('name') or item.get('shortName'), 240)
        try:
            quantity = int(item.get('quantity', 1) or 1)
        except (TypeError, ValueError, OverflowError):
            return None, 'Please enter a valid product quantity.'
        if quantity < 1 or quantity > 9999:
            return None, 'Product quantities must be between 1 and 9999.'
        if name:
            cleaned_item = {'name': name, 'quantity': quantity}
            for field, limit in (('description', 1000), ('specifications', 1000), ('category', 160), ('unitPrice', 80), ('unit_price', 80), ('price', 80), ('total', 80)):
                value = clean_text(item.get(field), limit)
                if value:
                    cleaned_item[field] = value
            cleaned_items.append(cleaned_item)
    cleaned['items'] = cleaned_items
    return cleaned, None


class AlipenRequestHandler(http.server.SimpleHTTPRequestHandler):
    server_version = 'AlipenWeb'
    sys_version = ''

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIRECTORY), **kwargs)

    def setup(self):
        super().setup()
        self.connection.settimeout(20)

    def end_headers(self):
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'strict-origin-when-cross-origin')
        self.send_header('X-Frame-Options', 'DENY')
        super().end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)
        path = urllib.parse.unquote(parsed.path)
        if path in ('/admin', '/admin/'):
            if not get_admin_session(self):
                self.redirect('/admin/login')
                return
            self.serve_file('admin.html', admin_page=True)
            return
        if path in ('/admin/login', '/admin/login/'):
            self.serve_file('admin-login.html', admin_page=True)
            return
        if path.startswith('/api/admin/'):
            self.handle_admin_api('GET', path, parsed.query)
            return
        if path == '/healthz':
            try:
                with database_connection() as conn:
                    conn.execute('SELECT 1')
                self.send_json(200, {'status': 'ok'})
            except Exception:
                self.send_json(503, {'status': 'unavailable'})
            return
        if path in ('/', '/index.html'):
            self.serve_file('index.html')
            return
        if path in ('/products', '/products/'):
            self.serve_file('products.html')
            return
        if path in ('/about', '/about/'):
            self.serve_file('about.html')
            return
        if path in ('/contact', '/contact/'):
            self.serve_file('contact.html')
            return
        if path.startswith('/products/'):
            slug = path[len('/products/'):].strip('/')
            if slug and '/' not in slug and not Path(slug).suffix and slug not in ('.', '..'):
                self.serve_product_detail()
                return
        if self.is_allowed_static_path(path):
            super().do_GET()
            return
        self.send_error(404, 'Not found')

    def do_HEAD(self):
        self._head_only = True
        try:
            self.do_GET()
        finally:
            self._head_only = False

    def copyfile(self, source, outputfile):
        if not getattr(self, '_head_only', False):
            super().copyfile(source, outputfile)

    def redirect(self, location):
        self.send_response(303)
        self.send_header('Location', location)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', '0')
        self.end_headers()

    @staticmethod
    def is_allowed_static_path(path):
        if not path.startswith('/') or '\\' in path or '\x00' in path:
            return False
        parts = Path(path.lstrip('/')).parts
        if not parts or any(part in ('.', '..') or part.startswith('.') for part in parts):
            return False
        if parts[0] == 'public':
            candidate = (DIRECTORY / Path(*parts)).resolve()
            public_dir = (DIRECTORY / 'public').resolve()
            if public_dir not in candidate.parents or not candidate.is_file():
                return False
            return candidate.suffix.lower() in STATIC_EXTENSIONS
        if len(parts) != 1 or parts[0] not in STATIC_ROOT_FILES:
            return False
        candidate = DIRECTORY / parts[0]
        return candidate.is_file()

    def do_POST(self):
        path = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
        if path.startswith('/api/admin/'):
            self.handle_admin_api('POST', path, '')
            return
        if path != '/api/quotes':
            self.send_json(404, {'success': False, 'message': 'Endpoint not found.'})
            return
        content_type = self.headers.get_content_type()
        if content_type != 'application/json':
            self.send_json(415, {'success': False, 'message': 'Please submit the form as JSON.'})
            return
        try:
            content_length = int(self.headers.get('Content-Length', '0'))
        except (TypeError, ValueError):
            self.send_json(400, {'success': False, 'message': 'Invalid request size.'})
            return
        if content_length <= 0:
            self.send_json(400, {'success': False, 'message': 'Request body is required.'})
            return
        if content_length > MAX_REQUEST_BYTES:
            self.send_json(413, {'success': False, 'message': 'Request is too large.'})
            return

        ip_address = client_ip(self)
        if is_rate_limited(ip_address):
            self.send_json(429, {'success': False, 'message': 'Too many requests. Please try again later.'})
            return
        try:
            raw = self.rfile.read(content_length)
            data = json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_json(400, {'success': False, 'message': 'Invalid JSON submission.'})
            return

        cleaned, validation_error = validate_submission(data)
        if validation_error:
            status = 400 if isinstance(data, dict) and data.get('website') else 422
            self.send_json(status, {'success': False, 'message': validation_error})
            return
        try:
            reference = save_quote(cleaned, ip_address)
        except Exception:
            print('Quote submission could not be saved to the database')
            self.send_json(503, {'success': False, 'message': 'We could not save your request right now. Please try WhatsApp or call us.'})
            return

        try:
            email_status = send_quote_emails(cleaned, reference)
        except Exception as error:
            logger.error('Quote email processing failed reference=%s exception_type=%s', reference, type(error).__name__)
            email_status = {'admin': 'failed', 'customer': 'failed'}
        self.send_json(201, {
            'success': True,
            'reference': reference,
            'message': 'Your quote request has been received.',
            'emailDelivery': email_status,
        })

    def do_PATCH(self):
        path = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
        if path.startswith('/api/admin/'):
            self.handle_admin_api('PATCH', path, '')
            return
        self.send_json(404, {'success': False, 'message': 'Endpoint not found.'})

    def do_DELETE(self):
        path = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
        if path.startswith('/api/admin/'):
            self.handle_admin_api('DELETE', path, '')
            return
        self.send_error(404, 'Endpoint not found.')

    def request_is_same_origin(self):
        origin = self.headers.get('Origin', '').strip().rstrip('/')
        fetch_site = self.headers.get('Sec-Fetch-Site', '').lower()
        if fetch_site and fetch_site not in ('same-origin', 'none'):
            return False
        if not origin:
            return True
        if SITE_URL:
            expected_origin = SITE_URL
        else:
            scheme = self.headers.get('X-Forwarded-Proto', 'http').split(',')[0].strip()
            expected_origin = f'{scheme}://{self.headers.get("Host", "")}'
        return secrets.compare_digest(origin.lower(), expected_origin.lower().rstrip('/'))

    def csrf_is_valid(self, session):
        supplied = self.headers.get('X-CSRF-Token', '')
        expected = session.get('csrf_token', '') if session else ''
        return bool(supplied and expected and secrets.compare_digest(supplied, expected))

    def secure_cookie(self):
        forwarded_proto = self.headers.get('X-Forwarded-Proto', '').split(',')[0].strip().lower()
        return SITE_URL.lower().startswith('https://') or forwarded_proto == 'https'

    def read_admin_json(self):
        if self.headers.get_content_type() != 'application/json':
            self.send_json(415, {'success': False, 'message': 'Please submit JSON.'})
            return None
        try:
            content_length = int(self.headers.get('Content-Length', '0'))
        except (TypeError, ValueError):
            self.send_json(400, {'success': False, 'message': 'Invalid request size.'})
            return None
        if content_length <= 0:
            self.send_json(400, {'success': False, 'message': 'Request body is required.'})
            return None
        if content_length > 160 * 1024:
            self.send_json(413, {'success': False, 'message': 'Request is too large.'})
            return None
        try:
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_json(400, {'success': False, 'message': 'Invalid JSON submission.'})
            return None
        if not isinstance(data, dict):
            self.send_json(400, {'success': False, 'message': 'Invalid request.'})
            return None
        return data

    def handle_admin_api(self, method, path, query_string=''):
        if method == 'POST' and path == '/api/admin/login':
            if not self.request_is_same_origin():
                self.send_json(403, {'success': False, 'message': 'Request origin was rejected.'})
                return
            ip_address = client_ip(self)
            if is_admin_login_limited(ip_address):
                self.send_json(429, {'success': False, 'message': 'Too many login attempts. Try again later.'})
                return
            data = self.read_admin_json()
            if data is None:
                return
            username = data.get('username')
            password = data.get('password')
            if (not isinstance(username, str) or not isinstance(password, str)
                    or not username or len(username) > 120 or not password or len(password) > 1024):
                self.send_json(401, {'success': False, 'message': 'Invalid username or password.'})
                return
            try:
                account = authenticate_admin(username, password)
            except Exception as error:
                logger.error('Admin authentication lookup failed exception_type=%s', type(error).__name__)
                self.send_json(503, {'success': False, 'message': 'Admin sign in is temporarily unavailable.'})
                return
            if not account:
                self.send_json(401, {'success': False, 'message': 'Invalid username or password.'})
                return

            clear_admin_login_attempts(ip_address)
            session_token, csrf_token = create_admin_session(account)
            cookie = (f'alipen_admin_session={session_token}; Path=/; HttpOnly; SameSite=Strict; '
                      f'Max-Age={ADMIN_SESSION_SECONDS}')
            if self.secure_cookie():
                cookie += '; Secure'
            self.send_json(200, {
                'success': True,
                'username': account['username'],
                'isPrimary': account['is_primary'],
                'csrfToken': csrf_token,
            }, headers={'Set-Cookie': cookie})
            return

        session = get_admin_session(self)
        if not session:
            self.send_json(401, {'success': False, 'message': 'Admin authentication required.'})
            return

        if method in ('POST', 'PATCH', 'DELETE'):
            if not self.request_is_same_origin():
                self.send_json(403, {'success': False, 'message': 'Request origin was rejected.'})
                return
            if not self.csrf_is_valid(session):
                self.send_json(403, {'success': False, 'message': 'Invalid CSRF token.'})
                return

        if method == 'GET' and path == '/api/admin/session':
            self.send_json(200, {
                'authenticated': True, 'username': session['username'],
                'isPrimary': session.get('is_primary', False), 'csrfToken': session['csrf_token'],
            })
            return

        if method == 'GET' and path == '/api/admin/invoices':
            params = urllib.parse.parse_qs(query_string, keep_blank_values=True)
            search = clean_text(params.get('search', [''])[0], 120)
            status = params.get('status', ['new'])[0]
            if status not in ('new', 'paid'):
                self.send_json(400, {'success': False, 'message': 'Invalid invoice status filter.'})
                return
            try:
                page = int(params.get('page', ['1'])[0])
            except (TypeError, ValueError):
                page = 0
            if page < 1 or page > 1_000_000:
                self.send_json(400, {'success': False, 'message': 'Invalid invoice page.'})
                return
            try:
                self.send_json(200, list_invoices(search=search, status=status, page=page))
            except Exception as error:
                logger.error('Invoice list unavailable exception_type=%s', type(error).__name__)
                self.send_json(503, {'success': False, 'message': 'Invoices are temporarily unavailable.'})
            return

        if method == 'POST' and path == '/api/admin/invoices':
            data = self.read_admin_json()
            if data is None:
                return
            try:
                invoice = create_invoice(data, session['username'])
            except InvoiceValidationError as error:
                self.send_json(422, {'success': False, 'message': str(error)})
                return
            except InvoiceNotFound as error:
                self.send_json(404, {'success': False, 'message': str(error)})
                return
            except Exception as error:
                logger.error('Invoice creation failed exception_type=%s', type(error).__name__)
                self.send_json(503, {'success': False, 'message': 'Invoice could not be saved.'})
                return
            self.send_json(201, {'success': True, 'invoice': invoice})
            return

        if path.startswith('/api/admin/invoices/'):
            suffix = path[len('/api/admin/invoices/'):]
            parts = suffix.split('/')
            if not parts[0].isdecimal() or len(parts[0]) > 18 or int(parts[0]) < 1:
                self.send_json(404, {'success': False, 'message': 'Invoice not found.'})
                return
            invoice_id = int(parts[0])
            if len(parts) == 2 and parts[1] == 'pdf' and method == 'GET':
                try:
                    invoice, content = get_invoice(invoice_id, include_pdf=True)
                except Exception as error:
                    logger.error('Invoice PDF lookup failed exception_type=%s', type(error).__name__)
                    self.send_json(503, {'success': False, 'message': 'Invoice PDF is temporarily unavailable.'})
                    return
                if not invoice or not content:
                    self.send_json(404, {'success': False, 'message': 'Invoice PDF not found.'})
                    return
                safe_number = re.sub(r'[^A-Za-z0-9-]', '', invoice['invoice_number'])
                self.send_response(200)
                self.send_header('Content-Type', 'application/pdf')
                self.send_header('Content-Length', str(len(content)))
                self.send_header('Content-Disposition', f'attachment; filename="{safe_number}.pdf"')
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                if not getattr(self, '_head_only', False):
                    self.wfile.write(content)
                return
            if len(parts) == 2 and parts[1] == 'paid' and method == 'POST':
                data = self.read_admin_json()
                if data is None:
                    return
                try:
                    invoice = mark_invoice_paid(invoice_id, data.get('payment_reference'), data.get('payment_note'), data.get('payment_date'))
                except InvoiceValidationError as error:
                    self.send_json(422, {'success': False, 'message': str(error)})
                    return
                except InvoiceNotFound as error:
                    self.send_json(404, {'success': False, 'message': str(error)})
                    return
                except InvoiceAlreadyPaid as error:
                    self.send_json(409, {'success': False, 'message': str(error)})
                    return
                except Exception as error:
                    logger.error('Invoice payment update failed exception_type=%s', type(error).__name__)
                    self.send_json(503, {'success': False, 'message': 'Invoice payment could not be recorded.'})
                    return
                self.send_json(200, {'success': True, 'invoice': invoice})
                return
            if len(parts) == 1 and method == 'GET':
                try:
                    invoice = get_invoice(invoice_id)
                except Exception as error:
                    logger.error('Invoice lookup failed exception_type=%s', type(error).__name__)
                    self.send_json(503, {'success': False, 'message': 'Invoice is temporarily unavailable.'})
                    return
                if not invoice:
                    self.send_json(404, {'success': False, 'message': 'Invoice not found.'})
                else:
                    self.send_json(200, {'invoice': invoice})
                return
            if len(parts) == 1 and method == 'PATCH':
                data = self.read_admin_json()
                if data is None:
                    return
                try:
                    invoice = update_invoice(invoice_id, data)
                except InvoiceValidationError as error:
                    self.send_json(422, {'success': False, 'message': str(error)})
                    return
                except InvoiceNotFound as error:
                    self.send_json(404, {'success': False, 'message': str(error)})
                    return
                except InvoicePaidFinancialChange as error:
                    self.send_json(409, {'success': False, 'message': str(error)})
                    return
                except Exception as error:
                    logger.error('Invoice update failed exception_type=%s', type(error).__name__)
                    self.send_json(503, {'success': False, 'message': 'Invoice could not be updated.'})
                    return
                self.send_json(200, {'success': True, 'invoice': invoice})
                return
            self.send_json(404, {'success': False, 'message': 'Invoice endpoint not found.'})
            return

        if method == 'GET' and path.startswith('/api/admin/documents/'):
            filename = path.rsplit('/', 1)[-1]
            extension = filename.rsplit('.', 1)[-1] if '.' in filename else ''
            template = INVOICE_TEMPLATES.get(extension)
            if not template or filename != f'invoice-template.{extension}':
                self.send_json(404, {'success': False, 'message': 'Document not found.'})
                return
            file_path, content_type = template
            try:
                content = file_path.read_bytes()
            except OSError:
                self.send_json(404, {'success': False, 'message': 'Document not found.'})
                return
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Content-Disposition', f'attachment; filename="{file_path.name}"')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            if not getattr(self, '_head_only', False):
                self.wfile.write(content)
            return

        if path == '/api/admin/users' or path.startswith('/api/admin/users/'):
            if not session.get('is_primary'):
                self.send_json(403, {'success': False, 'message': 'Primary administrator access required.'})
                return
            if method == 'GET' and path == '/api/admin/users':
                try:
                    self.send_json(200, {'users': list_admin_users()})
                except Exception as error:
                    logger.error('Admin user list unavailable exception_type=%s', type(error).__name__)
                    self.send_json(503, {'success': False, 'message': 'Administrator accounts are temporarily unavailable.'})
                return
            if method == 'POST' and path == '/api/admin/users':
                data = self.read_admin_json()
                if data is None:
                    return
                username = validate_admin_username(data.get('username'))
                password = data.get('password')
                if not username:
                    self.send_json(422, {'success': False, 'message': 'Username must be 3–120 characters and use letters, numbers, dots, underscores, or hyphens.'})
                    return
                if ADMIN_USERNAME and username.casefold() == ADMIN_USERNAME.casefold():
                    self.send_json(409, {'success': False, 'message': 'That username is reserved for the primary administrator.'})
                    return
                if not isinstance(password, str) or len(password) < 12 or len(password) > 1024:
                    self.send_json(422, {'success': False, 'message': 'Password must be at least 12 characters.'})
                    return
                try:
                    created = create_admin_user(username, _password_hasher.hash(password))
                except DuplicateAdminUsername:
                    self.send_json(409, {'success': False, 'message': 'That username is already in use.'})
                    return
                except Exception as error:
                    logger.error('Admin user creation failed exception_type=%s', type(error).__name__)
                    self.send_json(503, {'success': False, 'message': 'Administrator account could not be created.'})
                    return
                self.send_json(201, {'success': True, 'user': created})
                return
            if method == 'PATCH' and path.startswith('/api/admin/users/'):
                user_id_text = path[len('/api/admin/users/'):]
                if not user_id_text.isdecimal() or len(user_id_text) > 18:
                    self.send_json(404, {'success': False, 'message': 'Administrator account not found.'})
                    return
                data = self.read_admin_json()
                if data is None:
                    return
                username = None
                password_hash = None
                is_active = None
                if 'username' in data:
                    username = validate_admin_username(data['username'])
                    if not username:
                        self.send_json(422, {'success': False, 'message': 'Username must be 3–120 characters and use letters, numbers, dots, underscores, or hyphens.'})
                        return
                    if ADMIN_USERNAME and username.casefold() == ADMIN_USERNAME.casefold():
                        self.send_json(409, {'success': False, 'message': 'That username is reserved for the primary administrator.'})
                        return
                if 'password' in data:
                    password = data['password']
                    if not isinstance(password, str) or len(password) < 12 or len(password) > 1024:
                        self.send_json(422, {'success': False, 'message': 'Password must be at least 12 characters.'})
                        return
                    password_hash = _password_hasher.hash(password)
                if 'is_active' in data:
                    if not isinstance(data['is_active'], bool):
                        self.send_json(422, {'success': False, 'message': 'Account active state must be true or false.'})
                        return
                    is_active = data['is_active']
                if username is None and password_hash is None and is_active is None:
                    self.send_json(422, {'success': False, 'message': 'Provide a username, password, or active-state change.'})
                    return
                user_id = int(user_id_text)
                try:
                    updated = update_admin_user(user_id, username, password_hash, is_active)
                except DuplicateAdminUsername:
                    self.send_json(409, {'success': False, 'message': 'That username is already in use.'})
                    return
                except Exception as error:
                    logger.error('Admin user update failed exception_type=%s', type(error).__name__)
                    self.send_json(503, {'success': False, 'message': 'Administrator account could not be updated.'})
                    return
                if not updated:
                    self.send_json(404, {'success': False, 'message': 'Administrator account not found.'})
                    return
                revoke_admin_sessions(user_id)
                self.send_json(200, {'success': True, 'user': updated})
                return
            self.send_json(404, {'success': False, 'message': 'Admin endpoint not found.'})
            return

        if method == 'GET' and path == '/api/admin/overview':
            try:
                self.send_json(200, get_admin_overview())
            except Exception:
                self.send_json(503, {'success': False, 'message': 'Dashboard data is temporarily unavailable.'})
            return

        if method == 'GET' and path == '/api/admin/quotes':
            params = urllib.parse.parse_qs(query_string, keep_blank_values=True)
            search = clean_text(params.get('search', [''])[0], 120)
            status = params.get('status', ['all'])[0]
            follow_up = params.get('follow_up', ['all'])[0]
            if status not in ('all', 'new', 'in_progress', 'completed', 'won', 'lost'):
                self.send_json(400, {'success': False, 'message': 'Invalid status filter.'})
                return
            if follow_up not in ('all', 'due'):
                self.send_json(400, {'success': False, 'message': 'Invalid follow-up filter.'})
                return
            try:
                page = int(params.get('page', ['1'])[0])
                date_from_text = params.get('date_from', [''])[0]
                date_to_text = params.get('date_to', [''])[0]
                date_from = date.fromisoformat(date_from_text) if date_from_text else None
                date_to = date.fromisoformat(date_to_text) if date_to_text else None
            except (TypeError, ValueError):
                self.send_json(400, {'success': False, 'message': 'Invalid page or date filter.'})
                return
            if page < 1 or page > 1_000_000 or (date_from and date_to and date_from > date_to):
                self.send_json(400, {'success': False, 'message': 'Invalid page or date range.'})
                return
            try:
                data = list_admin_quotes(search, status, page, date_from=date_from, date_to=date_to, follow_up=follow_up)
                self.send_json(200, data)
            except Exception as error:
                logger.error('Admin quote list unavailable exception_type=%s', type(error).__name__)
                self.send_json(503, {'success': False, 'message': 'Quote requests are temporarily unavailable.'})
            return

        if method == 'GET' and path.startswith('/api/admin/quotes/') and path.endswith('/notes'):
            reference = path[len('/api/admin/quotes/'):-len('/notes')].strip('/')
            if not reference or '/' in reference:
                self.send_json(404, {'success': False, 'message': 'Quote request not found.'})
                return
            try:
                self.send_json(200, {'notes': list_quote_notes(reference)})
            except Exception as error:
                logger.error('Admin note list unavailable exception_type=%s', type(error).__name__)
                self.send_json(503, {'success': False, 'message': 'Private notes are temporarily unavailable.'})
            return

        if method == 'POST' and path.startswith('/api/admin/quotes/') and path.endswith('/notes'):
            reference = path[len('/api/admin/quotes/'):-len('/notes')].strip('/')
            if not reference or '/' in reference:
                self.send_json(404, {'success': False, 'message': 'Quote request not found.'})
                return
            data = self.read_admin_json()
            if data is None:
                return
            content = valid_admin_note(data.get('content'))
            if not content:
                self.send_json(422, {'success': False, 'message': 'Note must contain 1 to 5000 characters.'})
                return
            try:
                note = create_quote_note(reference, session['username'], content)
            except Exception as error:
                logger.error('Admin note create failed exception_type=%s', type(error).__name__)
                self.send_json(503, {'success': False, 'message': 'Private note could not be saved.'})
                return
            if not note:
                self.send_json(404, {'success': False, 'message': 'Quote request not found.'})
                return
            self.send_json(201, {'note': note})
            return

        if method in ('PATCH', 'DELETE') and path.startswith('/api/admin/notes/'):
            note_id_text = path[len('/api/admin/notes/'):]
            if not note_id_text.isdecimal() or len(note_id_text) > 18:
                self.send_json(404, {'success': False, 'message': 'Private note not found.'})
                return
            try:
                existing_note = get_quote_note(int(note_id_text))
            except Exception as error:
                logger.error('Admin note lookup failed exception_type=%s', type(error).__name__)
                self.send_json(503, {'success': False, 'message': 'Private note could not be updated.'})
                return
            if not existing_note:
                self.send_json(404, {'success': False, 'message': 'Private note not found.'})
                return
            if existing_note['author'] != session['username'] and not session.get('is_primary'):
                self.send_json(403, {'success': False, 'message': 'Only the note author or primary administrator may change this note.'})
                return
            if method == 'DELETE':
                delete_quote_note(int(note_id_text))
                self.send_json(200, {'success': True})
                return
            data = self.read_admin_json()
            if data is None:
                return
            content = valid_admin_note(data.get('content'))
            if not content:
                self.send_json(422, {'success': False, 'message': 'Note must contain 1 to 5000 characters.'})
                return
            try:
                self.send_json(200, {'note': update_quote_note(int(note_id_text), content)})
            except Exception as error:
                logger.error('Admin note update failed exception_type=%s', type(error).__name__)
                self.send_json(503, {'success': False, 'message': 'Private note could not be updated.'})
            return

        if method == 'PATCH' and path.startswith('/api/admin/follow-ups/'):
            reference = path[len('/api/admin/follow-ups/'):]
            if not reference or '/' in reference:
                self.send_json(404, {'success': False, 'message': 'Quote request not found.'})
                return
            data = self.read_admin_json()
            if data is None:
                return
            raw_date = data.get('date')
            follow_up_date = None
            if raw_date is not None:
                try:
                    follow_up_date = date.fromisoformat(raw_date)
                except (TypeError, ValueError):
                    self.send_json(422, {'success': False, 'message': 'Enter a valid follow-up date.'})
                    return
            note = data.get('note')
            if note is not None and (not isinstance(note, str) or len(note) > 1000):
                self.send_json(422, {'success': False, 'message': 'Reminder note must be 1000 characters or fewer.'})
                return
            completed = data.get('completed')
            if completed is not None and not isinstance(completed, bool):
                self.send_json(422, {'success': False, 'message': 'Reminder completion must be true or false.'})
                return
            if follow_up_date is None and completed is None:
                self.send_json(422, {'success': False, 'message': 'Provide a date or completion update.'})
                return
            try:
                result = update_follow_up(reference, follow_up_date, note.strip() if note is not None else None, completed)
            except Exception as error:
                logger.error('Follow-up update failed exception_type=%s', type(error).__name__)
                self.send_json(503, {'success': False, 'message': 'Follow-up reminder could not be updated.'})
                return
            if not result:
                self.send_json(404, {'success': False, 'message': 'Quote request not found.'})
                return
            self.send_json(200, {'follow_up': result})
            return

        if method == 'GET' and path.startswith('/api/admin/quotes/'):
            reference = path[len('/api/admin/quotes/'):]
            if reference and '/' not in reference:
                try:
                    quote = get_admin_quote(reference)
                except Exception:
                    self.send_json(503, {'success': False, 'message': 'Quote details are temporarily unavailable.'})
                    return
                if quote:
                    self.send_json(200, quote)
                else:
                    self.send_json(404, {'success': False, 'message': 'Quote request not found.'})
                return

        if method == 'PATCH' and path.startswith('/api/admin/quotes/') and path.endswith('/status'):
            reference = path[len('/api/admin/quotes/'):-len('/status')].strip('/')
            if not reference or '/' in reference:
                self.send_json(404, {'success': False, 'message': 'Quote request not found.'})
                return
            data = self.read_admin_json()
            if data is None:
                return
            status = data.get('status')
            if not isinstance(status, str) or status not in ADMIN_STATUSES:
                self.send_json(422, {'success': False, 'message': 'Invalid quote status.'})
                return
            try:
                updated = update_admin_quote_status(reference, status)
            except Exception:
                self.send_json(503, {'success': False, 'message': 'Quote status could not be updated.'})
                return
            if not updated:
                self.send_json(404, {'success': False, 'message': 'Quote request not found.'})
                return
            self.send_json(200, {'success': True, 'quote': updated})
            return

        if method == 'POST' and path == '/api/admin/logout':
            delete_admin_session(self)
            expired_cookie = 'alipen_admin_session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0'
            if self.secure_cookie():
                expired_cookie += '; Secure'
            self.send_json(200, {'success': True}, headers={'Set-Cookie': expired_cookie})
            return

        self.send_json(404, {'success': False, 'message': 'Admin endpoint not found.'})

    def do_OPTIONS(self):
        self.send_error(405, 'Method not allowed')

    def send_json(self, status, payload, headers=None):
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if not getattr(self, '_head_only', False):
            self.wfile.write(body)

    def serve_file(self, filename, admin_page=False):
        filepath = DIRECTORY / filename
        if not filepath.is_file():
            self.send_error(404, 'Not found')
            return
        content = filepath.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-store' if admin_page else 'no-cache')
        if admin_page:
            self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; form-action 'self'; base-uri 'self'; frame-ancestors 'none'; object-src 'none'")
        self.end_headers()
        if not getattr(self, '_head_only', False):
            self.wfile.write(content)

    def serve_product_detail(self):
        self.serve_file('product-detail.html')


class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def run_server():
    with ThreadingHTTPServer((HOST, PORT), AlipenRequestHandler) as httpd:
        print(f'Alipen website listening on {HOST}:{PORT}')
        httpd.serve_forever()


if __name__ == '__main__':
    try:
        init_database()
    except Exception:
        raise SystemExit('Unable to initialize PostgreSQL. Check DATABASE_URL and the database status.')
    run_server()
