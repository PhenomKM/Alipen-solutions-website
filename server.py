#!/usr/bin/env python3
"""Alipen Solutions Agency Ltd website and quote-request service."""

import http.server
import json
import html
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
from email.utils import parseaddr
from pathlib import Path

try:
    import psycopg
except ImportError:  # Allows static pages and syntax checks before dependencies are installed.
    psycopg = None


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
MAX_REQUEST_BYTES = 64 * 1024
RATE_LIMIT_REQUESTS = 8
RATE_LIMIT_WINDOW_SECONDS = 15 * 60
_rate_limit_lock = threading.Lock()
_request_times = defaultdict(deque)

STATIC_ROOT_FILES = {
    'index.html', 'products.html', 'product-detail.html', 'about.html',
    'contact.html', 'styles.css', 'app.js', 'products.js', 'script.js',
}
STATIC_EXTENSIONS = {
    '.html', '.css', '.js', '.png', '.jpg', '.jpeg', '.webp', '.gif',
    '.svg', '.ico', '.woff', '.woff2', '.ttf',
}
EMAIL_RE = re.compile(r'^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$')


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


def resend_email(to_address, subject, html_body, text_body):
    if not RESEND_API_KEY or not MAIL_FROM:
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
            return 'failed'
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
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
        status = 'not_configured'
        return {'admin': status, 'customer': status}
    admin_status = resend_email(ADMIN_EMAIL, f'New Alipen quote request — {reference}', admin_html, admin_text) if ADMIN_EMAIL else 'not_configured'
    customer_status = resend_email(data['email'], f'Quote request received — {reference}', customer_html, customer_text)
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
        super().end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)
        path = urllib.parse.unquote(parsed.path)
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
        if urllib.parse.urlsplit(self.path).path != '/api/quotes':
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
        except Exception:
            email_status = {'admin': 'failed', 'customer': 'failed'}
        self.send_json(201, {
            'success': True,
            'reference': reference,
            'message': 'Your quote request has been received.',
            'emailDelivery': email_status,
        })

    def do_OPTIONS(self):
        self.send_error(405, 'Method not allowed')

    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        if not getattr(self, '_head_only', False):
            self.wfile.write(body)

    def serve_file(self, filename):
        filepath = DIRECTORY / filename
        if not filepath.is_file():
            self.send_error(404, 'Not found')
            return
        content = filepath.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-cache')
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
