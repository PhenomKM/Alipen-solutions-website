import http.client
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
        server.ADMIN_EMAIL = 'admin@example.com'

        def resend_failure(*args, **kwargs):
            raise urllib.error.HTTPError('https://api.resend.com/emails', 403, 'unverified', {}, None)

        with patch.object(server.urllib.request, 'urlopen', side_effect=resend_failure):
            status, body, _ = self.request('POST', '/api/quotes', self.valid_payload())
        result = json.loads(body)
        self.assertEqual(status, 201)
        self.assertEqual(result['emailDelivery'], {'admin': 'failed', 'customer': 'failed'})

    def test_resend_success_is_reported_only_after_accepted_response(self):
        server.RESEND_API_KEY = 'test-key'
        server.MAIL_FROM = 'Alipen <test@example.com>'
        server.ADMIN_EMAIL = 'admin@example.com'

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
        self.assertEqual(send.call_args_list[0].args[0].full_url, 'https://api.resend.com/emails')
        self.assertEqual(send.call_args_list[0].args[0].headers['Authorization'], 'Bearer test-key')

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
