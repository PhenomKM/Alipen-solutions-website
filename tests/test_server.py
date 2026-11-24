import http.client
import html
import io
import json
import re
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

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


class FakeInvoiceConnection:
    """Small transactional PostgreSQL stand-in for exercising invoice services."""
    def __init__(self):
        self.statements = []
        self.quotes = {'ALIPEN-ABC123'}
        self.quote_status = {'ALIPEN-ABC123': 'new'}
        self.invoices = {}
        self.items = {}
        self.next_id = 1
        self.next_item_id = 1
        self.sequence = 0
        self.result_one = None
        self.result_all = []

    def __enter__(self): return self
    def __exit__(self, exc_type, exc, traceback): return False

    def execute(self, query, params=None):
        params = tuple(params or ())
        sql = ' '.join(query.split())
        upper = sql.upper()
        self.statements.append((sql, params))
        self.result_one, self.result_all = None, []
        if upper.startswith('SELECT REFERENCE FROM QUOTE_REQUESTS'):
            self.result_one = (params[0],) if params[0] in self.quotes else None
        elif upper.startswith('SELECT STATUS FROM QUOTE_REQUESTS'):
            self.result_one = (self.quote_status.get(params[0], 'new'),)
        elif upper.startswith('UPDATE QUOTE_REQUESTS SET STATUS = \'IN_PROGRESS\''):
            self.quote_status[params[0]] = 'in_progress'
        elif upper.startswith('UPDATE QUOTE_REQUESTS SET STATUS = \'COMPLETED\''):
            self.quote_status[params[0]] = 'completed'
        elif upper.startswith('SELECT COUNT(*) FROM INVOICES WHERE QUOTE_REFERENCE'):
            self.result_one = (sum(1 for invoice in self.invoices.values() if invoice.get('quote_reference') == params[0] and invoice.get('status') != 'paid'),)
        elif 'NEXTVAL(' in upper:
            self.sequence += 1
            self.result_one = (self.sequence,)
        elif upper.startswith('INSERT INTO INVOICES'):
            number = params[0]
            names = ('quote_reference', 'customer_name', 'customer_email', 'company_name', 'customer_address',
                     'invoice_date', 'due_date', 'currency', 'subtotal', 'discount_amount', 'tax_rate',
                     'tax_amount', 'total', 'notes', 'payment_instructions')
            invoice = dict(zip(names, params[1:16]))
            invoice.update(id=self.next_id, invoice_number=number, status='new', amount_paid=Decimal('0.00'),
                           payment_date=None, payment_reference='', payment_note='', created_by=params[16],
                           created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc), pdf_content=b'')
            self.next_id += 1
            self.invoices[invoice['id']] = invoice
            self.result_one = tuple(invoice.get(column) for column in server.INVOICE_COLUMNS)
        elif upper.startswith('INSERT INTO INVOICE_ITEMS'):
            invoice_id, position, slug, name, description, quantity, price, total = params
            self.items.setdefault(invoice_id, []).append({
                'id': self.next_item_id, 'product_slug': slug, 'name': name,
                'description': description, 'quantity': quantity,
                'unit_price': price, 'line_total': total, 'position': position,
            })
            self.next_item_id += 1
        elif upper.startswith('UPDATE INVOICES SET PDF_CONTENT'):
            self.invoices[params[1]]['pdf_content'] = params[0]
        elif upper.startswith('SELECT PDF_CONTENT FROM INVOICES'):
            self.result_one = (self.invoices[params[0]]['pdf_content'],) if params[0] in self.invoices else None
        elif upper.startswith('SELECT') and 'FROM INVOICE_ITEMS' in upper:
            self.result_all = [tuple(item.get(col) for col in server.INVOICE_ITEM_COLUMNS)
                               for item in self.items.get(params[0], [])]
        elif upper.startswith('SELECT') and 'FROM INVOICES' in upper:
            invoice_id = params[0]
            invoice = self.invoices.get(invoice_id)
            self.result_one = tuple(invoice.get(col) for col in server.INVOICE_COLUMNS) if invoice else None
        elif upper.startswith('UPDATE INVOICES SET STATUS'):
            paid_date, reference, note, invoice_id = params
            invoice = self.invoices[invoice_id]
            invoice.update(status='paid', amount_paid=invoice['total'], payment_date=paid_date,
                           payment_reference=reference, payment_note=note, updated_at=datetime.now(timezone.utc))
            self.result_one = tuple(invoice.get(col) for col in server.INVOICE_COLUMNS)
        elif upper.startswith('UPDATE INVOICES SET CUSTOMER_NAME'):
            fields = ('customer_name', 'customer_email', 'company_name', 'customer_address', 'invoice_date',
                      'due_date', 'currency', 'subtotal', 'discount_amount', 'tax_rate', 'tax_amount', 'total',
                      'notes', 'payment_instructions')
            invoice = self.invoices[params[-1]]
            invoice.update(dict(zip(fields, params[:-1])))
            invoice['updated_at'] = datetime.now(timezone.utc)
            self.result_one = tuple(invoice.get(col) for col in server.INVOICE_COLUMNS)
        elif upper.startswith('DELETE FROM INVOICE_ITEMS'):
            self.items[params[0]] = []
        return self

    def fetchone(self): return self.result_one
    def fetchall(self): return self.result_all


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
        server.RENDER_EXTERNAL_URL = ''
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
        listing.assert_called_once_with('Clinic', 'in_progress', 2, date_from=None, date_to=None, follow_up='all')
        with patch.object(server, 'get_admin_quote', return_value={'reference': 'ALIPEN-ABC123', 'items': []}):
            status, body, _ = self.request('GET', '/api/admin/quotes/ALIPEN-ABC123', headers=auth_headers)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['reference'], 'ALIPEN-ABC123')
        with patch.object(server, 'update_admin_quote_status', return_value={'reference': 'ALIPEN-ABC123', 'status': 'lost'}) as update:
            status, _, _ = self.request('PATCH', '/api/admin/quotes/ALIPEN-ABC123/status', {'status': 'lost'}, auth_headers)
            self.assertEqual(status, 403)
            status, body, _ = self.request('PATCH', '/api/admin/quotes/ALIPEN-ABC123/status', {'status': 'lost'}, {
                **auth_headers, 'Origin': f'http://127.0.0.1:{self.port}', 'X-CSRF-Token': csrf,
            })
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['quote']['status'], 'lost')
        update.assert_called_once_with('ALIPEN-ABC123', 'lost', None, '')
        with patch.object(server, 'update_admin_quote_status') as invalid_update:
            status, _, _ = self.request('PATCH', '/api/admin/quotes/ALIPEN-ABC123/status', {'status': {'unexpected': True}}, {
                **auth_headers, 'Origin': f'http://127.0.0.1:{self.port}', 'X-CSRF-Token': csrf,
            })
            self.assertEqual(status, 422)
            invalid_update.assert_not_called()
        status, _, _ = self.request('POST', '/api/admin/logout', {}, {
            **auth_headers, 'Origin': f'http://127.0.0.1:{self.port}', 'X-CSRF-Token': csrf,
        })
        self.assertEqual(status, 200)
        status, _, _ = self.request('GET', '/api/admin/overview', headers=auth_headers)
        self.assertEqual(status, 401)

    def test_dashboard_counts_use_database_aggregates_and_followups(self):
        connection = FakeConnection()
        connection.fetchone_result = (12, 4, 3, 1, 2, 2)
        connection.fetchall_result = []
        server.psycopg = SimpleNamespace(connect=lambda *args, **kwargs: connection)
        overview = server.get_admin_overview()
        sql = '\n'.join(statement for statement, _ in connection.statements)
        self.assertEqual((overview['total'], overview['new'], overview['in_progress'], overview['completed'], overview['follow_up_due']), (12, 4, 3, 1, 2))
        self.assertIn("status = 'lost'", sql)
        self.assertIn('follow_up_date <= %s', sql)
        self.assertIn('ORDER BY created_at DESC', sql)
        self.assertEqual(overview['recent'], [])
        self.assertEqual(overview['attention'], [])
        self.assertEqual(overview['follow_ups'], [])

    def test_admin_quote_date_status_search_and_followup_filters(self):
        status, body, headers = self.admin_login()
        cookie = headers.get('Set-Cookie').split(';', 1)[0]
        with patch.object(server, 'list_admin_quotes', return_value={'items': [], 'total': 0, 'page': 1, 'pageSize': 20}) as listing:
            status, _, _ = self.request('GET', '/api/admin/quotes?search=buyer%40example.com&status=won&date_from=2026-01-01&date_to=2026-01-31&follow_up=due', headers={'Cookie': cookie})
        self.assertEqual(status, 200)
        listing.assert_called_once_with('buyer@example.com', 'won', 1, date_from=datetime(2026, 1, 1).date(), date_to=datetime(2026, 1, 31).date(), follow_up='due')
        status, _, _ = self.request('GET', '/api/admin/quotes?date_from=2026-02-01&date_to=2026-01-01', headers={'Cookie': cookie})
        self.assertEqual(status, 400)

    def test_lost_quote_reason_is_csrf_protected_and_persisted(self):
        status, body, headers = self.admin_login()
        cookie = headers.get('Set-Cookie').split(';', 1)[0]
        csrf = json.loads(body)['csrfToken']
        with patch.object(server, 'update_admin_quote_status', return_value={'reference': 'ALIPEN-ABC123', 'status': 'lost'}) as update:
            status, _, _ = self.request('PATCH', '/api/admin/quotes/ALIPEN-ABC123/status', {
                'status': 'lost', 'lost_reason': 'Price too high', 'lost_explanation': 'Customer postponed purchase.'
            }, {'Cookie': cookie, 'Origin': f'http://127.0.0.1:{self.port}', 'X-CSRF-Token': csrf})
        self.assertEqual(status, 200)
        update.assert_called_once_with('ALIPEN-ABC123', 'lost', 'Price too high', 'Customer postponed purchase.')

    def test_quote_filter_database_query_applies_search_dates_status_and_pagination(self):
        connection = FakeConnection()
        connection.fetchone_result = (41,)
        connection.fetchall_result = []
        server.psycopg = SimpleNamespace(connect=lambda *args, **kwargs: connection)
        result = server.list_admin_quotes(
            'Clinic', 'completed', 3, date_from=datetime(2026, 3, 1).date(),
            date_to=datetime(2026, 3, 31).date(), follow_up='due', page_size=20,
        )
        self.assertEqual(result['total'], 41)
        count_sql, count_params = connection.statements[0]
        self.assertIn('reference ILIKE', count_sql)
        self.assertIn('facility ILIKE', count_sql)
        self.assertIn("status = %s", count_sql)
        self.assertIn('follow_up_date <= %s AND follow_up_completed = FALSE', count_sql)
        self.assertEqual(count_params[:5], ('%Clinic%',) * 4 + ('completed',))
        self.assertEqual(count_params[5], datetime(2026, 3, 1, tzinfo=server.BUSINESS_TIMEZONE))
        self.assertEqual(count_params[6], datetime(2026, 4, 1, tzinfo=server.BUSINESS_TIMEZONE))
        self.assertEqual(count_params[7], datetime.now(server.BUSINESS_TIMEZONE).date())
        self.assertEqual(connection.statements[2][1][-2:], (20, 40))

    def test_private_quote_notes_are_authenticated_csrf_protected_and_not_public(self):
        status, body, headers = self.admin_login()
        self.assertEqual(status, 200)
        cookie = headers.get('Set-Cookie').split(';', 1)[0]
        csrf = json.loads(body)['csrfToken']
        note = {'id': 9, 'author': 'unit-admin', 'content': 'Private pricing follow-up', 'created_at': '2026-11-24T10:00:00+00:00', 'updated_at': '2026-11-24T10:00:00+00:00'}
        with patch.object(server, 'create_quote_note', return_value=note) as create, patch.object(server, 'list_quote_notes', return_value=[note]) as listing:
            status, _, _ = self.request('POST', '/api/admin/quotes/ALIPEN-ABC123/notes', {'content': note['content']}, {
                'Cookie': cookie, 'Origin': f'http://127.0.0.1:{self.port}', 'X-CSRF-Token': csrf,
            })
            self.assertEqual(status, 201)
            create.assert_called_once_with('ALIPEN-ABC123', 'unit-admin', note['content'])
            status, body, _ = self.request('GET', '/api/admin/quotes/ALIPEN-ABC123/notes', headers={'Cookie': cookie})
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)['notes'][0]['content'], note['content'])
            listing.assert_called_once_with('ALIPEN-ABC123')
        status, _, _ = self.request('GET', '/api/admin/quotes/ALIPEN-ABC123/notes')
        self.assertEqual(status, 401)
        status, _, _ = self.request('POST', '/api/admin/quotes/ALIPEN-ABC123/notes', {'content': 'No token'}, {'Cookie': cookie, 'Origin': f'http://127.0.0.1:{self.port}'})
        self.assertEqual(status, 403)
        self.assertNotIn('Private pricing follow-up', server.format_items([])[0])

    def test_private_note_text_is_not_added_to_customer_quote_email(self):
        server.RESEND_API_KEY = 'test-key'
        server.MAIL_FROM = 'Alipen <quotes@example.com>'
        server.ADMIN_EMAIL = 'admin@example.com'
        response = MagicMock()
        response.status = 200
        response.read.return_value = b'{}'
        response.__enter__.return_value = response
        with patch('urllib.request.urlopen', return_value=response) as send:
            server.send_quote_emails({
                'name': 'Buyer', 'facility': 'Clinic', 'county': 'Nairobi', 'phone': '0712000000',
                'email': 'buyer@example.com', 'items': [], 'requirements': 'Please quote',
                'private_note': 'INTERNAL ONLY - do not include',
            }, 'ALIPEN-ABC123')
        email_payloads = [json.loads(call.args[0].data) for call in send.call_args_list]
        self.assertEqual(len(email_payloads), 2)
        self.assertNotIn('INTERNAL ONLY', json.dumps(email_payloads))

    def test_note_author_can_edit_and_delete_with_csrf(self):
        status, body, headers = self.admin_login()
        cookie = headers.get('Set-Cookie').split(';', 1)[0]
        csrf = json.loads(body)['csrfToken']
        auth = {'Cookie': cookie, 'Origin': f'http://127.0.0.1:{self.port}', 'X-CSRF-Token': csrf}
        existing = {'id': 12, 'author': 'unit-admin', 'content': 'Original', 'created_at': '2026-11-24T10:00:00+00:00', 'updated_at': '2026-11-24T10:00:00+00:00'}
        changed = {**existing, 'content': 'Revised'}
        with patch.object(server, 'get_quote_note', return_value=existing), patch.object(server, 'update_quote_note', return_value=changed) as edit:
            status, body, _ = self.request('PATCH', '/api/admin/notes/12', {'content': 'Revised'}, auth)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['note']['content'], 'Revised')
        edit.assert_called_once_with(12, 'Revised')
        with patch.object(server, 'get_quote_note', return_value=existing), patch.object(server, 'delete_quote_note', return_value=True) as delete:
            status, _, _ = self.request('DELETE', '/api/admin/notes/12', headers=auth)
        self.assertEqual(status, 200)
        delete.assert_called_once_with(12)

    def test_followup_create_complete_and_reschedule_require_csrf(self):
        status, body, headers = self.admin_login()
        cookie = headers.get('Set-Cookie').split(';', 1)[0]
        csrf = json.loads(body)['csrfToken']
        auth = {'Cookie': cookie, 'Origin': f'http://127.0.0.1:{self.port}', 'X-CSRF-Token': csrf}
        results = [
            {'reference': 'ALIPEN-ABC123', 'date': '2026-12-01', 'note': 'Call buyer', 'completed': False},
            {'reference': 'ALIPEN-ABC123', 'date': '2026-12-01', 'note': 'Call buyer', 'completed': True},
            {'reference': 'ALIPEN-ABC123', 'date': '2026-12-05', 'note': 'Call buyer', 'completed': False},
        ]
        with patch.object(server, 'update_follow_up', side_effect=results) as update:
            for payload in (
                {'date': '2026-12-01', 'note': 'Call buyer', 'completed': False},
                {'completed': True},
                {'date': '2026-12-05', 'note': 'Call buyer', 'completed': False},
            ):
                status, _, _ = self.request('PATCH', '/api/admin/follow-ups/ALIPEN-ABC123', payload, auth)
                self.assertEqual(status, 200)
        self.assertEqual(update.call_count, 3)
        status, _, _ = self.request('PATCH', '/api/admin/follow-ups/ALIPEN-ABC123', {'date': 'not-a-date'}, auth)
        self.assertEqual(status, 422)

    def test_invoice_templates_are_valid_and_download_only_after_admin_auth(self):
        for extension, mime in (('docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'), ('pdf', 'application/pdf')):
            path, expected_mime = server.INVOICE_TEMPLATES[extension]
            self.assertTrue(path.is_file())
            self.assertEqual(expected_mime, mime)
        with zipfile.ZipFile(server.INVOICE_TEMPLATES['docx'][0]) as docx:
            docx.testzip()
            self.assertIn('word/document.xml', docx.namelist())
            self.assertIn('word/media/logo.png', docx.namelist())
            xml = docx.read('word/document.xml')
            self.assertIn(b'Invoice number', xml)
            self.assertIn(b'Authorized by', xml)
            for name in docx.namelist():
                if name.endswith(('.xml', '.rels')):
                    import xml.etree.ElementTree as ET
                    ET.fromstring(docx.read(name))
        pdf = server.INVOICE_TEMPLATES['pdf'][0].read_bytes()
        self.assertTrue(pdf.startswith(b'%PDF-1.4'))
        self.assertTrue(pdf.rstrip().endswith(b'%%EOF'))
        self.assertIn(b'PAYMENT INSTRUCTIONS', pdf)
        xref_offset = int(pdf.rsplit(b'startxref\n', 1)[1].splitlines()[0])
        self.assertEqual(pdf[xref_offset:xref_offset + 4], b'xref')
        xref_lines = pdf[xref_offset:].splitlines()
        object_count = int(xref_lines[1].split()[1])
        for number, entry in enumerate(xref_lines[3:3 + object_count - 1], start=1):
            if entry.endswith(b' n '):
                offset = int(entry[:10])
                self.assertTrue(pdf[offset:].startswith(f'{number} 0 obj'.encode('ascii')))
        status, _, _ = self.request('GET', '/api/admin/documents/invoice-template.pdf')
        self.assertEqual(status, 401)
        status, body, headers = self.admin_login()
        cookie = headers.get('Set-Cookie').split(';', 1)[0]
        for extension, mime in (('docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'), ('pdf', 'application/pdf')):
            status, downloaded, response_headers = self.request('GET', f'/api/admin/documents/invoice-template.{extension}', headers={'Cookie': cookie})
            self.assertEqual(status, 200)
            self.assertEqual(response_headers.get('Content-Type'), mime)
            self.assertIn('attachment', response_headers.get('Content-Disposition'))
            self.assertTrue(downloaded)

    @staticmethod
    def invoice_payload(**updates):
        payload = {
            'customer_name': 'Invoice Buyer', 'customer_email': 'buyer@example.com',
            'company_name': 'Buyer Clinic', 'customer_address': 'Nairobi, Kenya',
            'invoice_date': '2026-11-24', 'due_date': '2026-12-24', 'currency': 'KES',
            'discount_amount': '500.00', 'tax_rate': '16.00', 'notes': 'Deliver to reception',
            'payment_instructions': '[Insert verified payment instructions]',
            'items': [
                {'product_slug': 'patient-monitor', 'name': 'Patient Monitor', 'description': 'Catalogue snapshot', 'quantity': '5', 'unit_price': '2000.00'},
                {'product_slug': None, 'name': 'Installation', 'description': 'Custom service', 'quantity': '3', 'unit_price': '1500.00'},
            ],
        }
        payload.update(updates)
        return payload

    def test_invoice_totals_are_decimal_safe_and_catalogue_items_are_validated(self):
        invoice = server.validate_invoice_payload(self.invoice_payload())
        self.assertEqual(invoice['items'][0]['line_total'], Decimal('10000.00'))
        self.assertEqual(invoice['items'][1]['line_total'], Decimal('4500.00'))
        self.assertEqual(invoice['subtotal'], Decimal('14500.00'))
        self.assertEqual(invoice['discount_amount'], Decimal('500.00'))
        self.assertEqual(invoice['tax_amount'], Decimal('2240.00'))
        self.assertEqual(invoice['total'], Decimal('16240.00'))
        self.assertEqual(invoice['items'][0]['product_slug'], 'patient-monitor')
        with self.assertRaises(server.InvoiceValidationError):
            server.validate_invoice_payload(self.invoice_payload(items=[{'name': 'Bad quantity', 'quantity': '0', 'unit_price': '1'}]))
        with self.assertRaises(server.InvoiceValidationError):
            server.validate_invoice_payload(self.invoice_payload(items=[{'name': 'Bad money', 'quantity': 1, 'unit_price': 'NaN'}]))
        with self.assertRaises(server.InvoiceValidationError):
            server.validate_invoice_payload(self.invoice_payload(items=[{'product_slug': 'not-a-catalogue-item', 'name': 'Unknown product', 'quantity': 1, 'unit_price': 1}]))

    def test_invoice_create_sequence_edit_payment_and_paid_financial_lock(self):
        connection = FakeInvoiceConnection()
        with patch.object(server, 'database_connection', return_value=connection):
            quote_invoice = server.create_invoice(self.invoice_payload(quote_reference='ALIPEN-ABC123'), 'unit-admin')
            self.assertEqual(connection.quote_status['ALIPEN-ABC123'], 'in_progress')
            standalone = server.create_invoice(self.invoice_payload(quote_reference=None), 'unit-admin')
            self.assertNotEqual(quote_invoice['invoice_number'], standalone['invoice_number'])
            self.assertEqual(quote_invoice['quote_reference'], 'ALIPEN-ABC123')
            self.assertIsNone(standalone['quote_reference'])
            self.assertEqual(quote_invoice['items'][0]['quantity'], '5.000')
            self.assertEqual(quote_invoice['items'][0]['description'], 'Catalogue snapshot')
            invoice_id = quote_invoice['id']
            stable_number = quote_invoice['invoice_number']

            edit = self.invoice_payload(quote_reference='ALIPEN-ABC123', customer_name='Corrected Buyer')
            updated = server.update_invoice(invoice_id, edit)
            self.assertEqual(updated['id'], invoice_id)
            self.assertEqual(updated['invoice_number'], stable_number)
            self.assertEqual(updated['customer_name'], 'Corrected Buyer')
            self.assertEqual(len(connection.invoices), 2)

            paid = server.mark_invoice_paid(invoice_id, 'BANK-REF-19', 'Paid in full', '2026-11-25')
            self.assertEqual(connection.quote_status['ALIPEN-ABC123'], 'completed')
            self.assertEqual(paid['status'], 'paid')
            self.assertEqual(paid['amount_paid'], paid['total'])
            self.assertEqual(paid['payment_date'], '2026-11-25')
            self.assertEqual(paid['payment_reference'], 'BANK-REF-19')
            self.assertEqual(paid['payment_note'], 'Paid in full')
            saved_pdf = connection.invoices[invoice_id]['pdf_content']
            self.assertTrue(saved_pdf.startswith(b'%PDF-1.4'))

            metadata_edit = self.invoice_payload(quote_reference='ALIPEN-ABC123', customer_name='Buyer Name Correction')
            metadata_edit['items'] = [dict(item) for item in metadata_edit['items']]
            metadata_edit['items'][0]['unit_price'] = '2000.00'
            metadata_edit['items'][1]['unit_price'] = '1500.00'
            paid_updated = server.update_invoice(invoice_id, metadata_edit)
            self.assertEqual(paid_updated['invoice_number'], stable_number)
            self.assertEqual(paid_updated['customer_name'], 'Buyer Name Correction')
            self.assertEqual(paid_updated['payment_reference'], 'BANK-REF-19')
            self.assertEqual(len(connection.invoices), 2)

            changed_finances = self.invoice_payload(quote_reference='ALIPEN-ABC123')
            changed_finances['items'][0]['unit_price'] = '1999.00'
            with self.assertRaises(server.InvoicePaidFinancialChange):
                server.update_invoice(invoice_id, changed_finances)
            with self.assertRaises(server.InvoiceAlreadyPaid):
                server.mark_invoice_paid(invoice_id, 'OVERWRITE', 'should not replace original')
            fetched, pdf_content = server.get_invoice(invoice_id, include_pdf=True)
            self.assertEqual(fetched['payment_reference'], 'BANK-REF-19')
            self.assertEqual(fetched['items'][0]['description'], 'Catalogue snapshot')
            self.assertEqual(pdf_content, connection.invoices[invoice_id]['pdf_content'])

    def test_quote_with_multiple_invoices_completes_only_after_all_are_paid(self):
        connection = FakeInvoiceConnection()
        server.psycopg = SimpleNamespace(connect=lambda *args, **kwargs: connection)
        first = server.create_invoice(self.invoice_payload(quote_reference='ALIPEN-ABC123'), 'unit-admin')
        second = server.create_invoice(self.invoice_payload(quote_reference='ALIPEN-ABC123'), 'unit-admin')
        server.mark_invoice_paid(first['id'], 'REF-1', '', '2026-11-25')
        self.assertEqual(connection.quote_status['ALIPEN-ABC123'], 'in_progress')
        server.mark_invoice_paid(second['id'], 'REF-2', '', '2026-11-25')
        self.assertEqual(connection.quote_status['ALIPEN-ABC123'], 'completed')

    def test_standalone_invoice_does_not_change_quote_status(self):
        connection = FakeInvoiceConnection()
        server.psycopg = SimpleNamespace(connect=lambda *args, **kwargs: connection)
        invoice = server.create_invoice(self.invoice_payload(), 'unit-admin')
        server.mark_invoice_paid(invoice['id'], 'REF', '', '2026-11-25')
        self.assertEqual(connection.quote_status['ALIPEN-ABC123'], 'new')

    def test_invoice_pdf_is_valid_branded_multipage_and_uses_stored_snapshot(self):
        from invoice_documents import invoice_pdf
        invoice = {
            'invoice_number': 'ALP-2026-000019', 'invoice_date': '2026-11-24', 'due_date': '2026-12-24',
            'customer_name': 'Buyer Clinic', 'customer_email': 'buyer@example.com', 'company_name': 'Buyer Ltd',
            'customer_address': 'Nairobi', 'quote_reference': 'ALIPEN-ABC123', 'currency': 'KES',
            'subtotal': '100.00', 'discount_amount': '0.00', 'tax_rate': '0.00', 'tax_amount': '0.00',
            'total': '100.00', 'amount_paid': '0.00', 'status': 'new',
            'payment_instructions': '[Insert verified payment instructions]', 'notes': 'Stored invoice note',
            'items': [{'name': f'Snapshot item {index}', 'description': 'Saved description unchanged', 'quantity': '1.000', 'unit_price': '10.00', 'line_total': '10.00'} for index in range(30)],
        }
        pdf = invoice_pdf(invoice)
        self.assertTrue(pdf.startswith(b'%PDF-1.4'))
        self.assertTrue(pdf.endswith(b'%%EOF'))
        self.assertIn(b'ALIPEN SOLUTIONS AGENCY LTD', pdf)
        self.assertIn(b'Snapshot item 0', pdf)
        self.assertIn(b'Stored invoice note', pdf)
        self.assertIn(b'[Insert verified payment instructions]', pdf)
        self.assertGreaterEqual(pdf.count(b'/Type /Page '), 3)
        xref_offset = int(pdf.rsplit(b'startxref\n', 1)[1].splitlines()[0])
        self.assertEqual(pdf[xref_offset:xref_offset + 4], b'xref')
        xref_lines = pdf[xref_offset:].splitlines()
        object_count = int(xref_lines[1].split()[1])
        for number, entry in enumerate(xref_lines[3:3 + object_count - 1], start=1):
            if entry.endswith(b' n '):
                offset = int(entry[:10])
                self.assertTrue(pdf[offset:].startswith(f'{number} 0 obj'.encode('ascii')))

    def test_invoice_endpoints_require_auth_csrf_and_protect_pdf(self):
        connection = FakeInvoiceConnection()
        db_patch = patch.object(server, 'database_connection', return_value=connection)
        db_patch.start()
        self.addCleanup(db_patch.stop)
        status, _, _ = self.request('GET', '/api/admin/invoices')
        self.assertEqual(status, 401)
        status, _, _ = self.request('GET', '/api/admin/invoices/1/pdf')
        self.assertEqual(status, 401)
        status, _, _ = self.request('POST', '/api/admin/invoices', self.invoice_payload())
        self.assertEqual(status, 401)

        status, body, headers = self.admin_login()
        cookie = headers.get('Set-Cookie').split(';', 1)[0]
        csrf = json.loads(body)['csrfToken']
        auth = {'Cookie': cookie, 'Origin': f'http://127.0.0.1:{self.port}', 'X-CSRF-Token': csrf}
        status, _, _ = self.request('POST', '/api/admin/invoices', self.invoice_payload(), {'Cookie': cookie, 'Origin': f'http://127.0.0.1:{self.port}'})
        self.assertEqual(status, 403)
        invalid = self.invoice_payload(customer_email='invalid address')
        status, _, _ = self.request('POST', '/api/admin/invoices', invalid, auth)
        self.assertEqual(status, 422)

        status, body, _ = self.request('POST', '/api/admin/invoices', self.invoice_payload(quote_reference='ALIPEN-ABC123'), auth)
        self.assertEqual(status, 201)
        invoice = json.loads(body)['invoice']
        invoice_id = invoice['id']
        status, body, _ = self.request('GET', f'/api/admin/invoices/{invoice_id}', headers={'Cookie': cookie})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['invoice']['items'][0]['quantity'], '5.000')
        status, pdf, response_headers = self.request('GET', f'/api/admin/invoices/{invoice_id}/pdf', headers={'Cookie': cookie})
        self.assertEqual(status, 200)
        self.assertEqual(response_headers.get('Content-Type'), 'application/pdf')
        self.assertIn('attachment', response_headers.get('Content-Disposition'))
        self.assertTrue(pdf.startswith(b'%PDF-1.4'))

        status, _, _ = self.request('PATCH', f'/api/admin/invoices/{invoice_id}', self.invoice_payload(), {'Cookie': cookie, 'Origin': f'http://127.0.0.1:{self.port}'})
        self.assertEqual(status, 403)
        status, body, _ = self.request('POST', f'/api/admin/invoices/{invoice_id}/paid', {
            'payment_date': '2026-11-25', 'payment_reference': 'BANK-REF-42', 'payment_note': 'Received',
        }, auth)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['invoice']['payment_reference'], 'BANK-REF-42')
        with patch.object(server, 'list_invoices', return_value={'items': [], 'total': 0, 'page': 1, 'pageSize': 20}) as listing:
            status, _, _ = self.request('GET', '/api/admin/invoices?status=paid&search=Buyer&page=1', headers={'Cookie': cookie})
        self.assertEqual(status, 200)
        listing.assert_called_once_with(search='Buyer', status='paid', page=1)
        status, _, _ = self.request('POST', f'/api/admin/invoices/{invoice_id}/paid', {}, auth)
        self.assertEqual(status, 409)

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
        migration_sql = '\n'.join(statement for statement, _ in self.db_connections[0].statements)
        self.assertIn('ADD COLUMN IF NOT EXISTS follow_up_date', migration_sql)
        self.assertIn('CREATE TABLE IF NOT EXISTS quote_notes', migration_sql)
        self.assertIn('quote_requests_follow_up_idx', migration_sql)
        self.assertIn('CREATE SEQUENCE IF NOT EXISTS alipen_invoice_number_seq', migration_sql)
        self.assertIn('CREATE TABLE IF NOT EXISTS invoices', migration_sql)
        self.assertIn('CREATE TABLE IF NOT EXISTS invoice_items', migration_sql)
        self.assertIn('NUMERIC(14, 2)', migration_sql)
        self.assertIn('CREATE INDEX IF NOT EXISTS invoice_items_invoice_position_idx', migration_sql)

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
                     '/private_documents/alipen-invoice-template.pdf',
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
        self.assertIn("'new'", insert[0])
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
        server.RENDER_EXTERNAL_URL = 'https://alipen-website.onrender.com'
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
            self.assertNotIn('Unit Price', message['html'])
            headers_html = re.search(r'<thead>(.*?)</thead>', message['html'], re.DOTALL).group(1)
            self.assertEqual(len(re.findall(r'<th\b', headers_html)), 3)
            self.assertNotIn('Total', headers_html)
            self.assertNotIn('KES 125,000', message['html'])
            self.assertNotIn('KES 250,000', message['html'])
            self.assertNotIn('KES 84,000', message['html'])
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
                '2',
            ])
            self.assertEqual(table_cells[1], [
                'ECG thermal paper', 'Z-fold and roll media for electrocardiographs.', '12',
            ])
            self.assertEqual(table_cells[2], [
                'QUIP 5-Litre Oxygen Concentrator',
                'Long description: medical-grade oxygen delivery for ward and home use.',
                '1',
            ])
        self.assertEqual(admin['to'], ['kayvo18@gmail.com'])
        self.assertEqual(customer['to'], ['buyer@example.com'])
        self.assertIn('New Alipen quote request — ALIPEN-ABC123', admin['subject'])
        self.assertIn('Quote request received — ALIPEN-ABC123', customer['subject'])
        self.assertIn('New Quote Request Received', admin['html'])
        self.assertIn('We’ve received your quote request', customer['html'])
        self.assertIn('Handle urgently', admin['html'])
        self.assertIn('Handle urgently', customer['html'])

    def test_quote_email_template_handles_absent_optional_fields_and_prices(self):
        table, text = server.format_items([{'name': 'Basic product', 'quantity': 3}])
        self.assertIn('Basic product', table)
        self.assertIn('>3<', table)
        self.assertIn('&mdash;', table)
        self.assertNotIn('Unit Price', table)
        self.assertNotIn('Total', table)
        self.assertNotIn('KES', table)
        self.assertEqual(text, '- Basic product | Quantity: 3')

    def test_public_logo_asset_is_served_at_email_url_path(self):
        status, body, headers = self.request('GET', '/public/images/logo.png')
        self.assertEqual(status, 200)
        self.assertEqual(headers.get('Content-Type'), 'image/png')
        self.assertEqual(body, (Path(server.DIRECTORY) / 'public/images/logo.png').read_bytes())

    def test_email_logo_url_uses_assigned_public_render_url(self):
        server.RENDER_EXTERNAL_URL = 'https://assigned-service.onrender.com'
        server.SITE_URL = 'https://custom-domain.example'
        self.assertEqual(server.email_logo_url(), 'https://assigned-service.onrender.com/public/images/logo.png')

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
