import http.client
import html
import io
import json
import re
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import server


class FakeConnection:
    def __init__(self):
        self.statements = []
        self.fetchone_result = None
        self.fetchall_result = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, query, params=None):
        self.statements.append((query, params))
        return self

    def fetchone(self):
        return self.fetchone_result

    def fetchall(self):
        return self.fetchall_result


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
        server.SITE_URL = ''
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

    def test_secondary_admin_authenticates_but_cannot_manage_other_accounts(self):
        from argon2 import PasswordHasher
        password = 'Additional-Admin-Password-2026'
        account_timestamp = datetime.now(timezone.utc)
        hasher = PasswordHasher()
        server.ADMIN_USERNAME = 'primary-admin'
        server.ADMIN_PASSWORD_HASH = hasher.hash('Primary-Password-2026')
        server._password_hasher = hasher
        with patch.object(server, 'get_admin_user_for_authentication', return_value=(44, 'staff-admin', hasher.hash(password), True, account_timestamp)):
            status, body, headers = self.request('POST', '/api/admin/login', {
                'username': 'staff-admin', 'password': password,
            }, {'Origin': f'http://127.0.0.1:{self.port}'})
        self.assertEqual(status, 200)
        result = json.loads(body)
        self.assertFalse(result['isPrimary'])
        self.assertNotIn('password_hash', body.decode())
        cookie = headers.get('Set-Cookie').split(';', 1)[0]
        auth_headers = {'Cookie': cookie}
        mutation_headers = {
            **auth_headers, 'Origin': f'http://127.0.0.1:{self.port}', 'X-CSRF-Token': result['csrfToken'],
        }
        with patch.object(server, 'get_admin_user_session_state', return_value=(True, account_timestamp)):
            status, body, _ = self.request('GET', '/api/admin/session', headers=auth_headers)
            self.assertEqual(status, 200)
            self.assertFalse(json.loads(body)['isPrimary'])
            status, _, _ = self.request('GET', '/api/admin/users', headers=auth_headers)
            self.assertEqual(status, 403)
            status, _, _ = self.request('POST', '/api/admin/users', {'username': 'other-admin', 'password': password}, mutation_headers)
            self.assertEqual(status, 403)
            status, _, _ = self.request('PATCH', '/api/admin/users/45', {'is_active': False}, mutation_headers)
            self.assertEqual(status, 403)

    def test_primary_admin_can_create_rename_reset_and_deactivate_accounts(self):
        from argon2 import PasswordHasher
        hasher = PasswordHasher()
        status, login_body, headers = self.admin_login()
        self.assertEqual(status, 200)
        cookie = headers.get('Set-Cookie').split(';', 1)[0]
        auth_headers = {
            'Cookie': cookie,
            'Origin': f'http://127.0.0.1:{self.port}',
            'X-CSRF-Token': json.loads(login_body)['csrfToken'],
        }
        safe_user = {'id': 23, 'username': 'clinic-admin', 'is_active': True, 'created_at': '2026-01-01T00:00:00+00:00'}
        with patch.object(server, 'list_admin_users', return_value=[safe_user]):
            status, body, _ = self.request('GET', '/api/admin/users', headers={'Cookie': cookie})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['users'], [safe_user])
        self.assertNotIn('password_hash', body.decode())

        status, _, _ = self.request('POST', '/api/admin/users', {
            'username': 'clinic-admin', 'password': 'New-Clinic-Admin-Password-2026',
        }, {'Cookie': cookie, 'Origin': f'http://127.0.0.1:{self.port}'})
        self.assertEqual(status, 403)
        with patch.object(server, 'create_admin_user', return_value=safe_user) as create_user:
            status, body, _ = self.request('POST', '/api/admin/users', {
                'username': 'clinic-admin', 'password': 'New-Clinic-Admin-Password-2026',
            }, auth_headers)
        self.assertEqual(status, 201)
        create_hash = create_user.call_args.args[1]
        self.assertTrue(create_hash.startswith('$argon2id$'))
        self.assertTrue(hasher.verify(create_hash, 'New-Clinic-Admin-Password-2026'))
        self.assertNotIn(create_hash, body.decode())
        self.assertNotIn('New-Clinic-Admin-Password-2026', body.decode())

        with patch.object(server, 'update_admin_user', return_value={**safe_user, 'username': 'clinic-admin-2', 'is_active': False}) as update_user, \
             patch.object(server, 'revoke_admin_sessions') as revoke:
            status, body, _ = self.request('PATCH', '/api/admin/users/23', {
                'username': 'clinic-admin-2', 'password': 'Reset-Clinic-Admin-Password-2026', 'is_active': False,
            }, auth_headers)
        self.assertEqual(status, 200)
        update_args = update_user.call_args.args
        self.assertEqual(update_args[0], 23)
        self.assertEqual(update_args[1], 'clinic-admin-2')
        self.assertTrue(hasher.verify(update_args[2], 'Reset-Clinic-Admin-Password-2026'))
        self.assertFalse(update_args[3])
        revoke.assert_called_once_with(23)
        self.assertNotIn('password_hash', body.decode())
        self.assertNotIn('Reset-Clinic-Admin-Password-2026', body.decode())

    def test_password_reset_or_deactivation_invalidates_existing_secondary_sessions(self):
        from datetime import timedelta
        timestamp = datetime.now(timezone.utc)
        token, _ = server.create_admin_session({
            'id': 91, 'username': 'staff-account', 'is_primary': False, 'updated_at': timestamp,
        })
        handler = SimpleNamespace(headers={'Cookie': f'alipen_admin_session={token}'})
        with patch.object(server, 'get_admin_user_session_state', return_value=(True, timestamp)):
            self.assertIsNotNone(server.get_admin_session(handler))
        with patch.object(server, 'get_admin_user_session_state', return_value=(True, timestamp + timedelta(seconds=1))):
            self.assertIsNone(server.get_admin_session(handler))

        token, _ = server.create_admin_session({
            'id': 92, 'username': 'disabled-account', 'is_primary': False, 'updated_at': timestamp,
        })
        handler = SimpleNamespace(headers={'Cookie': f'alipen_admin_session={token}'})
        with patch.object(server, 'get_admin_user_session_state', return_value=(False, timestamp)):
            self.assertIsNone(server.get_admin_session(handler))

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
        self.assertTrue(any('CREATE TABLE IF NOT EXISTS admin_users' in statement for statement, _ in self.db_connections[0].statements))
        self.assertTrue(any('CREATE UNIQUE INDEX IF NOT EXISTS admin_users_username_lower_unique' in statement for statement, _ in self.db_connections[0].statements))

    def test_admin_user_database_helpers_return_only_safe_fields(self):
        created_at = datetime.now(timezone.utc)
        connection = FakeConnection()
        connection.fetchone_result = (31, 'new-admin', True, created_at)
        connection.fetchall_result = [(31, 'new-admin', True, created_at)]
        server.psycopg = SimpleNamespace(connect=lambda *args, **kwargs: connection)

        created = server.create_admin_user('new-admin', '$argon2id$private-hash')
        self.assertEqual(created['username'], 'new-admin')
        self.assertNotIn('password_hash', created)
        self.assertNotIn('$argon2id$', json.dumps(created))
        insert_sql, insert_params = connection.statements[-1]
        self.assertIn('INSERT INTO admin_users', insert_sql)
        self.assertIn('%s', insert_sql)
        self.assertEqual(insert_params, ('new-admin', '$argon2id$private-hash'))

        listed = server.list_admin_users()
        self.assertEqual(listed[0]['username'], 'new-admin')
        self.assertNotIn('password_hash', listed[0])
        list_sql = connection.statements[-1][0]
        self.assertIn('SELECT id, username, is_active, created_at', list_sql)
        self.assertNotIn('password_hash', list_sql)

        connection.fetchone_result = (31, 'renamed-admin', False, created_at)
        updated = server.update_admin_user(31, username='renamed-admin', is_active=False)
        self.assertFalse(updated['is_active'])
        self.assertNotIn('password_hash', updated)
        update_sql, update_params = connection.statements[-1]
        self.assertIn('UPDATE admin_users SET', update_sql)
        self.assertEqual(update_params, ('renamed-admin', False, 31))

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

    def test_quote_emails_render_matching_items_and_escape_customer_content(self):
        server.RESEND_API_KEY = 'test-key'
        server.MAIL_FROM = 'Alipen <test@example.com>'
        server.ADMIN_EMAIL = 'kayvo18@gmail.com'
        server.SITE_URL = 'http://localhost:3000'
        sample = {
            'name': '<Buyer & Co>', 'facility': 'Long Name Medical Facility',
            'facilityType': 'Hospital', 'county': 'Nairobi', 'phone': '+254700123456',
            'email': 'buyer@example.com', 'requirements': '<script>no</script> Handle urgently',
            'items': [
                {'name': 'Advanced multi-parameter bedside patient monitor for high-acuity wards',
                 'description': 'Long description & specifications <include> ECG, SpO2, NIBP, respiration and dual-channel temperature.',
                 'quantity': 2, 'unitPrice': 'KES 125,000', 'total': 'KES 250,000'},
                {'name': 'ECG thermal paper', 'description': 'Z-fold and roll media for electrocardiographs.', 'quantity': 12},
                {'name': 'QUIP 5-Litre Oxygen Concentrator',
                 'description': 'Long description: medical-grade oxygen delivery for ward and home use.',
                 'quantity': 1, 'unitPrice': 'KES 84,000'},
            ],
        }
        class AcceptedResponse:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): return False

        cleaned, validation_error = server.validate_submission(sample)
        self.assertIsNone(validation_error)
        self.assertEqual(cleaned['items'], sample['items'])
        with patch.object(server.urllib.request, 'urlopen', return_value=AcceptedResponse()) as send:
            result = server.send_quote_emails(cleaned, 'ALIPEN-ABC123')
        self.assertEqual(result, {'admin': 'accepted', 'customer': 'accepted'})
        admin, customer = [json.loads(call.args[0].data) for call in send.call_args_list]
        for message in (admin, customer):
            self.assertIn('https://alipen-website.onrender.com/public/images/logo.png', message['html'])
            self.assertIn('ALIPEN-ABC123', message['html'])
            self.assertIn('&lt;Buyer &amp; Co&gt;', message['html'])
            self.assertIn('Long Name Medical Facility', message['html'])
            self.assertIn('<table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="width:100%;table-layout:fixed', message['html'])
            self.assertIn('<th align="left"', message['html'])
            self.assertIn('Description / Specifications', message['html'])
            self.assertIn('<th align="center"', message['html'])
            self.assertIn('Quantity', message['html'])
            self.assertIn('Advanced multi-parameter bedside patient monitor', message['html'])
            self.assertIn('Long description &amp; specifications &lt;include&gt;', message['html'])
            self.assertIn('ECG thermal paper', message['html'])
            self.assertIn('Z-fold and roll media for electrocardiographs.', message['html'])
            self.assertIn('QUIP 5-Litre Oxygen Concentrator', message['html'])
            self.assertIn('Long description: medical-grade oxygen delivery', message['html'])
            self.assertIn('>2</td>', message['html'])
            self.assertIn('>12</td>', message['html'])
            self.assertIn('>1</td>', message['html'])
            self.assertIn('KES 125,000', message['html'])
            self.assertIn('KES 250,000', message['html'])
            self.assertIn('KES 84,000', message['html'])
            self.assertIn('ECG thermal paper', message['text'])
            self.assertIn('Quantity: 12', message['text'])
            self.assertEqual(message['from'], 'Alipen <test@example.com>')
            self.assertNotIn('<script>', message['html'])
            self.assertNotIn('<Buyer & Co>', message['html'])
            table_body = re.search(r'Description / Specifications.*?<tbody>(.*?)</tbody>', message['html'], re.DOTALL).group(1)
            rows = re.findall(r'<tr>(.*?)</tr>', table_body, re.DOTALL)
            self.assertEqual(len(rows), 3)
            table_cells = [[html.unescape(re.sub(r'<[^>]+>', '', cell)).strip()
                            for cell in re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)]
                           for row in rows]
            self.assertEqual(table_cells[0], [
                'Advanced multi-parameter bedside patient monitor for high-acuity wards',
                'Long description & specifications <include> ECG, SpO2, NIBP, respiration and dual-channel temperature.',
                '2', 'KES 125,000', 'KES 250,000',
            ])
            self.assertEqual(table_cells[1], [
                'ECG thermal paper', 'Z-fold and roll media for electrocardiographs.', '12', '—', '—',
            ])
            self.assertEqual(table_cells[2], [
                'QUIP 5-Litre Oxygen Concentrator',
                'Long description: medical-grade oxygen delivery for ward and home use.',
                '1', 'KES 84,000', '—',
            ])
        self.assertEqual(admin['to'], ['kayvo18@gmail.com'])
        self.assertEqual(customer['to'], ['buyer@example.com'])
        self.assertIn('New Alipen quote request — ALIPEN-ABC123', admin['subject'])
        self.assertIn('Quote request received — ALIPEN-ABC123', customer['subject'])
        self.assertIn('New Quote Request Received', admin['html'])
        self.assertIn('We’ve received your quote request', customer['html'])
        self.assertIn('Handle urgently', admin['html'])
        self.assertIn('Handle urgently', customer['html'])
        self.assertIn('New Quote Request Received', admin['html'])
        self.assertIn('Handle urgently', admin['html'])
        self.assertIn('Handle urgently', customer['html'])

    def test_quote_email_template_handles_absent_optional_fields_and_prices(self):
        table, text = server.format_items([{'name': 'Basic product', 'quantity': 3}])
        self.assertIn('Basic product', table)
        self.assertIn('>3<', table)
        self.assertIn('&mdash;', table)
        self.assertNotIn('KES', table)
        self.assertEqual(text, '- Basic product | Quantity: 3')

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
