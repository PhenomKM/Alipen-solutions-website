#!/usr/bin/env python3
"""Alipen Solutions Agency Ltd website and quote-request service."""

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
ADMIN_QUOTE_COLUMNS = (
    'reference', 'name', 'facility', 'facility_type', 'county', 'phone',
    'email', 'items', 'requirements', 'status', 'created_at',
)
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
    quote['status'] = quote.get('status') or 'received'
    return quote


def get_admin_overview():
    with database_connection() as conn:
        row = conn.execute('''
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE status IS NULL OR status IN ('', 'new', 'received')) AS new,
                COUNT(*) FILTER (WHERE status = 'in_progress') AS in_progress,
                COUNT(*) FILTER (WHERE status = 'completed') AS completed
            FROM quote_requests
        ''').fetchone()
        recent_rows = conn.execute(f'''
            SELECT {', '.join(ADMIN_QUOTE_COLUMNS)}
            FROM quote_requests
            ORDER BY created_at DESC NULLS LAST, id DESC
            LIMIT %s
        ''', (5,)).fetchall()
    return {
        'total': row[0],
        'new': row[1],
        'in_progress': row[2],
        'completed': row[3],
        'recent': [serialize_admin_quote(item) for item in recent_rows],
    }


def list_admin_quotes(search='', status='all', page=1, page_size=20):
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
    if not items:
        return '<li>General catalogue and procurement inquiry</li>'
    rows = []
    for item in items:
        name = escape(item.get('name') or 'Medical product')
        quantity = escape(item.get('quantity', 1))
        rows.append(f'<li><strong>{name}</strong> — Quantity: {quantity}</li>')
    return ''.join(rows)


def email_layout(title, body):
    logo_url = f'{SITE_URL}/public/images/logo.png' if SITE_URL else ''
    logo = (f'<img src="{escape(logo_url)}" alt="Alipen Solutions Agency Ltd" '
            'style="height:72px;width:auto;object-fit:contain;" />') if logo_url else ''
    return f'''<!doctype html><html><body style="margin:0;background:#f4f7fb;font-family:Arial,sans-serif;color:#1e293b">
    <div style="max-width:680px;margin:24px auto;background:#fff;border-radius:14px;overflow:hidden;border:1px solid #e2e8f0">
      <div style="padding:22px 28px;border-bottom:1px solid #e2e8f0;text-align:center">{logo}</div>
      <div style="padding:28px"><h1 style="margin:0 0 12px;font-size:24px;color:#0d3c78">{escape(title)}</h1>{body}</div>
      <div style="padding:18px 28px;background:#0f172a;color:#cbd5e1;font-size:13px">Alipen Solutions Agency Ltd • +254 712 272 463 • Nairobi, Kenya</div>
    </div></body></html>'''


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
    items_html = format_items(data.get('items', []))
    shared_details = f'''
      <p>We have received your quote request. Peter Ogettoh's team will review it shortly.</p>
      <table style="width:100%;border-collapse:collapse;margin:18px 0">
        <tr><td><strong>Reference</strong></td><td>{escape(reference)}</td></tr>
        <tr><td><strong>Facility</strong></td><td>{escape(data['facility'])}</td></tr>
        <tr><td><strong>Contact</strong></td><td>{escape(data['name'])}</td></tr>
        <tr><td><strong>Phone</strong></td><td>{escape(data['phone'])}</td></tr>
        <tr><td><strong>Location</strong></td><td>{escape(data.get('county', ''))}</td></tr>
      </table>
      <h3>Requested items</h3><ul style="line-height:1.8;padding-left:20px">{items_html}</ul>
    '''
    customer_html = email_layout('Your quote request has been received', shared_details +
        '<p>Please keep this reference for follow-up. For additional information, reply to this email or call +254 712 272 463.</p>')
    customer_text = (f"Dear {data['name']},\n\nWe received your quote request.\nReference: {reference}\n"
                     f"Facility: {data['facility']}\nPhone: {data['phone']}\n\nAlipen Solutions Agency Ltd\n+254 712 272 463")

    admin_body = shared_details + f'<p><strong>Email:</strong> {escape(data["email"])}</p><p><strong>Facility type:</strong> {escape(data.get("facilityType", ""))}</p><p><strong>Additional requirements:</strong><br />{escape(data.get("requirements", "None"))}</p>'
    admin_html = email_layout(f'New quote request — {reference}', admin_body)
    admin_text = (f"New quote request {reference}\nName: {data['name']}\nFacility: {data['facility']}\n"
                  f"Email: {data['email']}\nPhone: {data['phone']}\nRequirements: {data.get('requirements', '')}")

    if not RESEND_API_KEY or not MAIL_FROM:
        missing = []
        if not RESEND_API_KEY:
            missing.append('RESEND_API_KEY')
        if not MAIL_FROM:
            missing.append('MAIL_FROM')
        logger.error('Quote emails not sent reference=%s missing configuration=%s', reference, ','.join(missing))
        status = 'not_configured'
        return {'admin': status, 'customer': status}
    if ADMIN_EMAIL:
        admin_status = resend_email(
            ADMIN_EMAIL, f'New Alipen quote request — {reference}', admin_html, admin_text,
            notification_type='admin', reference=reference,
        )
    else:
        logger.error('Admin quote notification not sent reference=%s missing configuration=ADMIN_EMAIL', reference)
        admin_status = 'not_configured'
    customer_status = resend_email(
        data['email'], f'Quote request received — {reference}', customer_html, customer_text,
        notification_type='customer', reference=reference,
    )
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
            cleaned_items.append({'name': name, 'quantity': quantity})
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
        if content_length > 4096:
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

        if method in ('POST', 'PATCH'):
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
            if status not in ('all', 'new', 'in_progress', 'completed'):
                self.send_json(400, {'success': False, 'message': 'Invalid status filter.'})
                return
            try:
                page = int(params.get('page', ['1'])[0])
            except (TypeError, ValueError):
                page = 0
            if page < 1 or page > 1_000_000:
                self.send_json(400, {'success': False, 'message': 'Invalid page number.'})
                return
            try:
                self.send_json(200, list_admin_quotes(search, status, page))
            except Exception:
                self.send_json(503, {'success': False, 'message': 'Quote requests are temporarily unavailable.'})
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
            if status not in ADMIN_STATUSES:
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
