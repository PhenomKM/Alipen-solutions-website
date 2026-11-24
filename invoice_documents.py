"""Render stored invoice snapshots as self-contained branded PDF documents."""

from pathlib import Path
from decimal import Decimal
import re
import zlib

from tools.generate_invoice_templates import decode_png_rgb


LOGO = Path(__file__).resolve().parent / 'public' / 'images' / 'logo.png'
PAGE_WIDTH, PAGE_HEIGHT = 595, 842
BLUE = (0.086, 0.322, 0.627)
NAVY = (0.071, 0.235, 0.431)
INK = (0.12, 0.17, 0.24)
MUTED = (0.38, 0.43, 0.50)
PALE = (0.93, 0.96, 0.985)
RULE = (0.84, 0.87, 0.90)


def _pdf_text(value):
    raw = str(value or '').encode('cp1252', 'replace')
    escaped = []
    for byte in raw:
        if byte in (ord('('), ord(')'), ord('\\')):
            escaped.append('\\' + chr(byte))
        elif byte < 32 or byte > 126:
            escaped.append(f'\\{byte:03o}')
        else:
            escaped.append(chr(byte))
    return '(' + ''.join(escaped) + ')'


def _wrap(value, max_chars):
    words = str(value or '').split()
    lines, line = [], ''
    for word in words:
        if len(word) > max_chars:
            if line:
                lines.append(line)
                line = ''
            lines.extend(word[i:i + max_chars] for i in range(0, len(word), max_chars))
            continue
        candidate = f'{line} {word}'.strip()
        if len(candidate) > max_chars and line:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines or ['']


def invoice_pdf(invoice):
    """Return a valid multi-page PDF from a serialized invoice and item snapshot."""
    logo_width, logo_height, logo_pixels = decode_png_rgb(LOGO)
    logo_bytes = zlib.compress(logo_pixels)
    pages = []
    commands = []
    page_number = 0

    def text(x, y, value, size=9, color=INK, font='F1'):
        commands.append(f'{color[0]} {color[1]} {color[2]} rg BT /{font} {size} Tf {x} {y} Td {_pdf_text(value)} Tj ET')

    def line(x1, y1, x2, y2, color=RULE, weight=0.7):
        commands.append(f'{weight} w {color[0]} {color[1]} {color[2]} RG {x1} {y1} m {x2} {y2} l S')

    def rect(x, y, width, height, color):
        commands.append(f'{color[0]} {color[1]} {color[2]} rg {x} {y} {width} {height} re f')

    def start_page(first=False):
        nonlocal commands, page_number
        if commands:
            pages.append('\n'.join(commands).encode('ascii'))
        commands = []
        page_number += 1
        commands.append(f'q 112 0 0 35 42 {785 if first else 782} cm /Logo Do Q')
        text(42, 766 if first else 762, 'ALIPEN SOLUTIONS AGENCY LTD', 12, BLUE, 'F2')
        text(42, 748 if first else 744, 'Nairobi, Kenya  |  +254 712 272 463  |  info@alipen.co.ke', 8, MUTED)
        text(394, 792 if first else 792, 'INVOICE', 19, NAVY, 'F2')
        text(394, 773, invoice['invoice_number'], 10, BLUE, 'F2')
        line(42, 733 if first else 728, 553, 733 if first else 728, BLUE, 2)
        line(42, 42, 553, 42)
        text(42, 26, f"{invoice['invoice_number']}  |  {invoice.get('status', 'new').upper()}", 8, MUTED)
        text(510, 26, f'Page {page_number}', 8, MUTED)

    def money(value):
        return f"{invoice['currency']} {value}"

    start_page(True)
    text(42, 704, 'BILL TO', 8, BLUE, 'F2')
    text(42, 686, invoice['customer_name'], 12, NAVY, 'F2')
    y = 670
    for value in (invoice.get('company_name'), invoice.get('customer_email'), invoice.get('customer_address')):
        if value:
            for part in _wrap(value, 48)[:2]:
                text(42, y, part, 9, INK)
                y -= 13
    rect(355, 651, 198, 62, PALE)
    text(369, 695, 'INVOICE DATE', 7, MUTED, 'F2')
    text(369, 680, str(invoice['invoice_date']), 10, NAVY, 'F2')
    text(369, 665, 'DUE DATE', 7, MUTED, 'F2')
    text(454, 665, str(invoice['due_date']), 7, MUTED, 'F2')
    if invoice.get('quote_reference'):
        text(42, min(y - 4, 637), f"Quote reference: {invoice['quote_reference']}", 8, MUTED)

    items = invoice.get('items') or []
    table_top = 610
    header_height = 25
    row_y = table_top
    rows = [
        (42, 'ITEM', 'F2'), (239, 'DESCRIPTION', 'F2'),
        (402, 'QTY', 'F2'), (441, 'UNIT PRICE', 'F2'), (506, 'TOTAL', 'F2'),
    ]

    def table_header(top):
        rect(42, top - header_height, 511, header_height, BLUE)
        for x, label, font in rows:
            text(x + 7, top - 16, label, 7, (1, 1, 1), font)

    table_header(row_y)
    row_y -= header_height
    for index, item in enumerate(items):
        name_lines = _wrap(item['name'], 30)
        desc_lines = _wrap(item.get('description', ''), 25)
        line_count = max(1, len(name_lines), len(desc_lines))
        row_height = max(32, line_count * 10 + 18)
        if row_y - row_height < 210:
            start_page(False)
            row_y = 742
            table_header(row_y)
            row_y -= header_height
        base_y = row_y - 15
        for line_no, value in enumerate(name_lines):
            text(49, base_y - line_no * 10, value, 8, NAVY if line_no == 0 else INK, 'F2' if line_no == 0 else 'F1')
        for line_no, value in enumerate(desc_lines):
            text(246, base_y - line_no * 10, value, 7.5, MUTED)
        text(409, base_y, str(item['quantity']), 8)
        text(441, base_y, str(item['unit_price']), 8)
        text(506, base_y, str(item['line_total']), 8, NAVY, 'F2')
        line(42, row_y - row_height, 553, row_y - row_height)
        if index % 2 == 1:
            rect(42, row_y - row_height + 1, 511, 0.5, PALE)
        row_y -= row_height

    if row_y < 250:
        start_page(False)
        row_y = 742
    totals_top = row_y - 10
    rect(322, totals_top - 154, 231, 154, PALE)
    text(337, totals_top - 20, 'Subtotal', 9, MUTED)
    text(472, totals_top - 20, money(invoice['subtotal']), 9, INK)
    text(337, totals_top - 39, 'Discount', 9, MUTED)
    text(472, totals_top - 39, f"- {money(invoice['discount_amount'])}", 9, INK)
    tax_rate = invoice.get('tax_rate', '0.00')
    text(337, totals_top - 58, f'Tax ({tax_rate}%)', 9, MUTED)
    text(472, totals_top - 58, money(invoice['tax_amount']), 9, INK)
    line(337, totals_top - 68, 538, totals_top - 68)
    rect(322, totals_top - 105, 231, 30, BLUE)
    text(337, totals_top - 95, 'TOTAL DUE', 9, (1, 1, 1), 'F2')
    text(458, totals_top - 95, money(invoice['total']), 11, (1, 1, 1), 'F2')
    amount_paid = invoice.get('amount_paid', '0.00')
    balance_due = max(Decimal('0.00'), Decimal(str(invoice['total'])) - Decimal(str(amount_paid)))
    text(337, totals_top - 120, 'Amount paid', 8, MUTED)
    text(458, totals_top - 120, money(amount_paid), 8, INK)
    text(337, totals_top - 139, 'Balance due', 8, MUTED)
    text(458, totals_top - 139, money(f'{balance_due:.2f}'), 8, NAVY, 'F2')

    section_y = min(totals_top - 22, 390)

    def section(title, value, y):
        if y < 75:
            start_page(False)
            y = 735
        text(42, y, title, 8, BLUE, 'F2')
        y -= 15
        for part in _wrap(value, 62):
            if y < 60:
                start_page(False)
                y = 735
                text(42, y, f'{title} (continued)', 8, BLUE, 'F2')
                y -= 15
            text(42, y, part, 8, INK)
            y -= 12
        return y - 12

    instructions = invoice.get('payment_instructions') or '[Insert verified payment instructions]'
    payment_lines = [instructions]
    if invoice.get('payment_date'):
        payment_lines.append(f"Payment received: {invoice['payment_date']}")
    if invoice.get('payment_reference'):
        payment_lines.append(f"Payment reference: {invoice['payment_reference']}")
    if invoice.get('payment_note'):
        payment_lines.append(f"Payment note: {invoice['payment_note']}")
    section_y = section('PAYMENT INSTRUCTIONS', ' | '.join(payment_lines), section_y)
    section('NOTES & TERMS', invoice.get('notes') or 'Thank you for your business.', section_y)
    if commands:
        pages.append('\n'.join(commands).encode('ascii'))

    # PDF page objects use direct references so the file needs no third-party library.
    objects = [None, None,
               b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
               b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>',
               (f'<< /Type /XObject /Subtype /Image /Width {logo_width} /Height {logo_height} '
                f'/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode /Length {len(logo_bytes)} >>\nstream\n'.encode('ascii')
                + logo_bytes + b'\nendstream')]
    page_ids = []
    for index, stream in enumerate(pages):
        page_id = len(objects) + 1
        stream_id = page_id + 1
        page_ids.append(page_id)
        objects.append((f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] '
                        f'/Resources << /Font << /F1 3 0 R /F2 4 0 R >> /XObject << /Logo 5 0 R >> >> '
                        f'/Contents {stream_id} 0 R >>').encode('ascii'))
        objects.append(b'<< /Length ' + str(len(stream)).encode('ascii') + b' >>\nstream\n' + stream + b'\nendstream')
    objects[0] = b'<< /Type /Catalog /Pages 2 0 R >>'
    kids = ' '.join(f'{page_id} 0 R' for page_id in page_ids)
    objects[1] = f'<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>'.encode('ascii')
    pdf = bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf.extend(f'{number} 0 obj\n'.encode('ascii') + obj + b'\nendobj\n')
    xref = len(pdf)
    pdf.extend(f'xref\n0 {len(offsets)}\n'.encode('ascii'))
    pdf.extend(b'0000000000 65535 f \n')
    for offset in offsets[1:]:
        pdf.extend(f'{offset:010d} 00000 n \n'.encode('ascii'))
    pdf.extend(f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF'.encode('ascii'))
    return bytes(pdf)
