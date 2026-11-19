import http.client
import io
import json
import re
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import server


class FakeConnection:
    def __init__(self):
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, query, params=None):
        self.statements.append((query, params))
        return self


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = server.ThreadingHTTPServer(('127.0.0.1', 0), server.AlipenRequestHandler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=3)

    def setUp(self):
        server._request_times.clear()
        server._admin_login_attempts.clear()
        server._admin_sessions.clear()
        self.db_connections = []

        def connect(*args, **kwargs):
            connection = FakeConnection()
            self.db_connections.append(connection)
            return connection

        server.DATABASE_URL = 'postgresql://unit-test.invalid/test'
        server.psycopg = SimpleNamespace(connect=connect)
        server.RESEND_API_KEY = ''
        server.MAIL_FROM = ''
        server.ADMIN_EMAIL = ''
        server.ADMIN_USERNAME = ''
        server.ADMIN_PASSWORD_HASH = ''

    def admin_login(self, username='unit-admin', password='Test-Admin-Password-2026'):
        from argon2 import PasswordHasher
        server.ADMIN_USERNAME = username
        server.ADMIN_PASSWORD_HASH = PasswordHasher().hash(password)
        server._password_hasher = PasswordHasher()
        return self.request('POST', '/api/admin/login', {'username': username, 'password': password}, {
            'Origin': f'http://127.0.0.1:{self.port}',
        })

    def test_admin_requires_login_and_never_serves_dashboard_to_unauthenticated_users(self):
        status, _, headers = self.request('GET', '/admin')
        self.assertEqual(status, 303)
        self.assertEqual(headers.get('Location'), '/admin/login')
        status, body, _ = self.request('GET', '/admin/login')
        self.assertEqual(status, 200)
        self.assertIn(b'Admin sign in', body)
        status, _, _ = self.request('GET', '/api/admin/quotes')
        self.assertEqual(status, 401)
        status, _, _ = self.request('GET', '/admin.html')
        self.assertEqual(status, 404)

    def test_admin_login_cookie_and_session_security(self):
        status, body, headers = self.admin_login()
        self.assertEqual(status, 200)
        result = json.loads(body)
        self.assertTrue(result['csrfToken'])
        cookie = headers.get('Set-Cookie')
        self.assertIn('HttpOnly', cookie)
        self.assertIn('SameSite=Strict', cookie)
        self.assertNotIn('Secure', cookie)  # local HTTP; production HTTPS sets this flag
        with patch.object(server, 'get_admin_overview', return_value={'total': 0, 'new': 0, 'in_progress': 0, 'completed': 0, 'recent': []}):
            status, _, _ = self.request('GET', '/api/admin/overview', headers={'Cookie': cookie.split(';', 1)[0]})
        self.assertEqual(status, 200)

    def test_admin_login_rejects_bad_credentials_and_limits_attempts(self):
        self.admin_login()
        cookie = None
        # Keep the configured hash while submitting invalid credentials.
        for _ in range(server.ADMIN_LOGIN_LIMIT):
            status, _, _ = self.request('POST', '/api/admin/login', {'username': 'unit-admin', 'password': 'wrong'}, {
                'Origin': f'http://127.0.0.1:{self.port}',
            })
            self.assertEqual(status, 401)
        status, _, _ = self.request('POST', '/api/admin/login', {'username': 'unit-admin', 'password': 'wrong'}, {
            'Origin': f'http://127.0.0.1:{self.port}',
        })
        self.assertEqual(status, 429)

    def test_admin_quote_listing_search_detail_update_csrf_and_logout(self):
        status, body, headers = self.admin_login()
        self.assertEqual(status, 200)
        cookie = headers.get('Set-Cookie').split(';', 1)[0]
        csrf = json.loads(body)['csrfToken']
        auth_headers = {'Cookie': cookie}
        with patch.object(server, 'list_admin_quotes', return_value={'items': [], 'total': 0, 'page': 2, 'pageSize': 20}) as listing:
            status, body, _ = self.request('GET', '/api/admin/quotes?search=Clinic&status=in_progress&page=2', headers=auth_headers)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['page'], 2)
        listing.assert_called_once_with('Clinic', 'in_progress', 2)
        with patch.object(server, 'get_admin_quote', return_value={'reference': 'ALIPEN-ABC123', 'items': []}):
            status, body, _ = self.request('GET', '/api/admin/quotes/ALIPEN-ABC123', headers=auth_headers)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['reference'], 'ALIPEN-ABC123')
        with patch.object(server, 'update_admin_quote_status', return_value={'reference': 'ALIPEN-ABC123', 'status': 'completed'}) as update:
            status, _, _ = self.request('PATCH', '/api/admin/quotes/ALIPEN-ABC123/status', {'status': 'completed'}, auth_headers)
            self.assertEqual(status, 403)
            status, body, _ = self.request('PATCH', '/api/admin/quotes/ALIPEN-ABC123/status', {'status': 'completed'}, {
                **auth_headers, 'Origin': f'http://127.0.0.1:{self.port}', 'X-CSRF-Token': csrf,
            })
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['quote']['status'], 'completed')
        update.assert_called_once_with('ALIPEN-ABC123', 'completed')
        status, _, _ = self.request('POST', '/api/admin/logout', {}, {
            **auth_headers, 'Origin': f'http://127.0.0.1:{self.port}', 'X-CSRF-Token': csrf,
        })
        self.assertEqual(status, 200)
        status, _, _ = self.request('GET', '/api/admin/overview', headers=auth_headers)
        self.assertEqual(status, 401)

    def test_admin_production_cookie_secure_and_origin_validation(self):
        server.SITE_URL = 'https://alipen.example'
        from argon2 import PasswordHasher
        server.ADMIN_USERNAME = 'unit-admin'
        server.ADMIN_PASSWORD_HASH = PasswordHasher().hash('Test-Admin-Password-2026')
        server._password_hasher = PasswordHasher()
        status, _, headers = self.request('POST', '/api/admin/login', {
            'username': 'unit-admin', 'password': 'Test-Admin-Password-2026',
        }, {'Origin': 'https://alipen.example'})
        self.assertEqual(status, 200)
        self.assertIn('Secure', headers.get('Set-Cookie'))
        status, _, _ = self.request('POST', '/api/admin/login', {
            'username': 'unit-admin', 'password': 'Test-Admin-Password-2026',
        }, {'Origin': 'https://evil.example'})
        self.assertEqual(status, 403)
        server.SITE_URL = ''

    def request(self, method, path, payload=None, headers=None, body=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        request_headers = dict(headers or {})
        if payload is not None:
            body = json.dumps(payload).encode('utf-8')
            request_headers.setdefault('Content-Type', 'application/json')
        if body is not None:
            request_headers.setdefault('Content-Length', str(len(body)))
        connection.request(method, path, body=body, headers=request_headers)
        response = connection.getresponse()
        result = response.read()
        status = response.status
        response_headers = response.headers
        connection.close()
        return status, result, response_headers

    @staticmethod
    def valid_payload(**updates):
        payload = {
            'name': 'Test Contact',
            'facility': 'Test Clinic',
            'county': 'Nairobi',
            'phone': '+254700000000',
            'email': 'test@example.com',
            'facilityType': 'Clinic',
            'requirements': 'Testing only',
            'items': [{'name': 'Test ECG', 'quantity': 2}],
        }
        payload.update(updates)
        return payload

    def test_health_and_existing_page_routes(self):
        status, body, _ = self.request('GET', '/healthz')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {'status': 'ok'})
        for path in ('/', '/products', '/products/contec-e12-ecg', '/about', '/contact'):
            with self.subTest(path=path):
                status, body, _ = self.request('GET', path)
                self.assertEqual(status, 200)
                self.assertIn(b'<!DOCTYPE HTML', body.upper())

    def test_database_initialization_creates_quote_table(self):
        server.init_database()
        self.assertIn('CREATE TABLE IF NOT EXISTS quote_requests', self.db_connections[0].statements[0][0])

    def test_static_assets_are_available_but_internal_files_are_not(self):
        status, body, _ = self.request('GET', '/public/images/catalogue/image_56.png')
        self.assertEqual(status, 200)
        self.assertTrue(body.startswith(b'\x89PNG'))
        for path in ('/server.py', '/.env', '/.env.example', '/requirements.txt', '/README.md',
                     '/alipen_quotes.db', '/brand-assets/Logo.jpeg', '/__pycache__/server.pyc',
                     '/public/../server.py', '/%2e%2e/server.py'):
            with self.subTest(path=path):
                status, _, _ = self.request('GET', path)
                self.assertEqual(status, 404)

    def test_same_origin_api_does_not_enable_cors(self):
        status, _, headers = self.request('GET', '/healthz')
        self.assertEqual(status, 200)
        self.assertNotIn('Access-Control-Allow-Origin', headers)
        status, _, _ = self.request('OPTIONS', '/api/quotes')
        self.assertEqual(status, 405)

    def test_quote_validation_and_honeypot(self):
        cases = (
            (self.valid_payload(name=''), 422),
            (self.valid_payload(email='invalid'), 422),
            (self.valid_payload(county=''), 422),
            (self.valid_payload(website='filled by bot'), 400),
            (self.valid_payload(website={'bot': True}), 400),
            (self.valid_payload(items=[{'name': 'ECG', 'quantity': -1}]), 422),
        )
        for payload, expected in cases:
            with self.subTest(expected=expected, payload=payload):
                status, _, _ = self.request('POST', '/api/quotes', payload)
                self.assertEqual(status, expected)
        self.assertFalse(self.db_connections)

    def test_request_limits_and_bad_json(self):
        status, _, _ = self.request('POST', '/api/quotes', headers={'Content-Type': 'application/json'},
                                    body=b'{bad json')
        self.assertEqual(status, 400)
        status, _, _ = self.request('POST', '/api/quotes', headers={
            'Content-Type': 'application/json', 'Content-Length': str(server.MAX_REQUEST_BYTES + 1),
        })
        self.assertEqual(status, 413)
        status, _, _ = self.request('POST', '/api/quotes', headers={'Content-Type': 'text/plain'}, body=b'{}')
        self.assertEqual(status, 415)

    def test_quote_is_inserted_and_email_status_is_explicit(self):
        payload = self.valid_payload(name='<Test Contact>')
        status, body, _ = self.request('POST', '/api/quotes', payload)
        result = json.loads(body)
        self.assertEqual(status, 201)
        self.assertRegex(result['reference'], r'^ALIPEN-[A-F0-9]{6}$')
        self.assertEqual(result['emailDelivery'], {'admin': 'not_configured', 'customer': 'not_configured'})
        self.assertNotIn('test@example.com', result)
        insert = self.db_connections[0].statements[0]
        self.assertIn('INSERT INTO quote_requests', insert[0])
        self.assertEqual(insert[1][1], '<Test Contact>')
        self.assertEqual(json.loads(insert[1][-2]), [{'name': 'Test ECG', 'quantity': 2}])

    def test_database_error_does_not_expose_customer_data(self):
        def fail_connect(*args, **kwargs):
            raise RuntimeError('database credential detail must stay private')

        server.psycopg = SimpleNamespace(connect=fail_connect)
        status, body, _ = self.request('POST', '/api/quotes', self.valid_payload())
        self.assertEqual(status, 503)
        self.assertNotIn(b'test@example.com', body)
        self.assertNotIn(b'credential detail', body)

    def test_resend_failure_does_not_undo_saved_quote(self):
        server.RESEND_API_KEY = 'test-key'
        server.MAIL_FROM = 'Alipen <test@example.com>'
        server.ADMIN_EMAIL = 'kayvo18@gmail.com'

        def resend_failure(*args, **kwargs):
            body = json.dumps({'name': 'validation_error', 'message': 'Rejected customer@example.com'}).encode()
            raise urllib.error.HTTPError('https://api.resend.com/emails', 403, 'unverified', {}, io.BytesIO(body))

        with self.assertLogs('server', level='WARNING') as logs, patch.object(server.urllib.request, 'urlopen', side_effect=resend_failure) as send:
            status, body, _ = self.request('POST', '/api/quotes', self.valid_payload())
        result = json.loads(body)
        self.assertEqual(status, 201)
        self.assertEqual(result['emailDelivery'], {'admin': 'failed', 'customer': 'failed'})
        self.assertEqual(send.call_count, 2)
        self.assertTrue(any('http_status=403' in line and 'validation_error' in line for line in logs.output))
        self.assertNotIn('customer@example.com', '\n'.join(logs.output))
        self.assertNotIn('test-key', '\n'.join(logs.output))

    def test_resend_success_is_reported_only_after_accepted_response(self):
        server.RESEND_API_KEY = 'test-key'
        server.MAIL_FROM = 'Alipen <test@example.com>'
        server.ADMIN_EMAIL = 'kayvo18@gmail.com'

        class AcceptedResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

        with patch.object(server.urllib.request, 'urlopen', return_value=AcceptedResponse()) as send:
            result = server.send_quote_emails(self.valid_payload(), 'ALIPEN-ABC123')
        self.assertEqual(result, {'admin': 'accepted', 'customer': 'accepted'})
        self.assertEqual(send.call_count, 2)
        admin_request, customer_request = [call.args[0] for call in send.call_args_list]
        self.assertEqual(admin_request.full_url, 'https://api.resend.com/emails')
        self.assertEqual(admin_request.method, 'POST')
        self.assertEqual(admin_request.get_header('Authorization'), 'Bearer test-key')
        self.assertEqual(admin_request.get_header('Content-type'), 'application/json')
        admin_payload = json.loads(admin_request.data)
        customer_payload = json.loads(customer_request.data)
        self.assertEqual(admin_payload['from'], 'Alipen <test@example.com>')
        self.assertEqual(admin_payload['to'], ['kayvo18@gmail.com'])
        self.assertEqual(customer_payload['to'], ['test@example.com'])
        self.assertEqual(customer_payload['from'], admin_payload['from'])
        self.assertIn('ALIPEN-ABC123', admin_payload['subject'])
        self.assertIn('ALIPEN-ABC123', customer_payload['text'])

    def test_missing_resend_configuration_is_logged_and_quote_still_succeeds(self):
        with self.assertLogs('server', level='ERROR') as logs:
            status, body, _ = self.request('POST', '/api/quotes', self.valid_payload())
        self.assertEqual(status, 201)
        self.assertEqual(json.loads(body)['emailDelivery'], {'admin': 'not_configured', 'customer': 'not_configured'})
        self.assertTrue(any('RESEND_API_KEY' in line and 'MAIL_FROM' in line for line in logs.output))

    def test_unexpected_email_exception_keeps_saved_quote_successful(self):
        with patch.object(server, 'send_quote_emails', side_effect=RuntimeError('provider error')):
            status, body, _ = self.request('POST', '/api/quotes', self.valid_payload())
        self.assertEqual(status, 201)
        self.assertEqual(json.loads(body)['emailDelivery'], {'admin': 'failed', 'customer': 'failed'})

    def test_rate_limit(self):
        start = 1000
        for index in range(server.RATE_LIMIT_REQUESTS):
            self.assertFalse(server.is_rate_limited('test-ip', now=start + index))
        self.assertTrue(server.is_rate_limited('test-ip', now=start + server.RATE_LIMIT_REQUESTS))

    def test_catalogue_public_asset_references_exist(self):
        refs = set()
        for pattern in ('*.html', '*.js', '*.css'):
            for file_path in Path(server.DIRECTORY).glob(pattern):
                source = file_path.read_text(encoding='utf-8', errors='ignore')
                refs.update(re.findall(r'''["']((?:public/|/images/)[^"']+)["']''', source))
        missing = [ref for ref in refs if not (Path(server.DIRECTORY) / ref.lstrip('/')).is_file()]
        self.assertEqual(missing, [])


if __name__ == '__main__':
    unittest.main()
