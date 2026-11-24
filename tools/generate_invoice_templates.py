#!/usr/bin/env python3
"""Build editable Alipen invoice templates without external document libraries."""

from pathlib import Path
import struct
import zlib
from zipfile import ZIP_DEFLATED, ZipFile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'private_documents'
LOGO = ROOT / 'public' / 'images' / 'logo.png'
BLUE = '1652A0'
NAVY = '12345A'
PALE = 'EAF1F9'
GRAY = '596579'


def make_docx():
    OUT.mkdir(exist_ok=True)
    ns = {
        'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
        'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
        'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
        'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
        'pic': 'http://schemas.openxmlformats.org/drawingml/2006/picture',
    }
    for prefix, uri in ns.items():
        ET.register_namespace(prefix, uri)
    q = lambda prefix, name: f'{{{ns[prefix]}}}{name}'
    doc = ET.Element(q('w', 'document'))
    body = ET.SubElement(doc, q('w', 'body'))

    def paragraph(text='', bold=False, size=20, color=NAVY, align=None):
        p = ET.SubElement(body, q('w', 'p'))
        ppr = ET.SubElement(p, q('w', 'pPr'))
        if align:
            ET.SubElement(ppr, q('w', 'jc'), {q('w', 'val'): align})
        run = ET.SubElement(p, q('w', 'r'))
        rpr = ET.SubElement(run, q('w', 'rPr'))
        ET.SubElement(rpr, q('w', 'color'), {q('w', 'val'): color})
        ET.SubElement(rpr, q('w', 'sz'), {q('w', 'val'): str(size)})
        if bold:
            ET.SubElement(rpr, q('w', 'b'))
        ET.SubElement(run, q('w', 't')).text = text
        return p

    image_p = ET.SubElement(body, q('w', 'p'))
    run = ET.SubElement(image_p, q('w', 'r'))
    drawing = ET.SubElement(run, q('w', 'drawing'))
    inline = ET.SubElement(drawing, q('wp', 'inline'), {'distT': '0', 'distB': '0', 'distL': '0', 'distR': '0'})
    ET.SubElement(inline, q('wp', 'extent'), {'cx': '1650000', 'cy': '510309'})
    ET.SubElement(inline, q('wp', 'docPr'), {'id': '1', 'name': 'Alipen official logo'})
    graphic = ET.SubElement(inline, q('a', 'graphic'))
    graphic_data = ET.SubElement(graphic, q('a', 'graphicData'), {'uri': ns['pic']})
    pic = ET.SubElement(graphic_data, q('pic', 'pic'))
    nv = ET.SubElement(pic, q('pic', 'nvPicPr'))
    ET.SubElement(nv, q('pic', 'cNvPr'), {'id': '0', 'name': 'Alipen logo'})
    ET.SubElement(nv, q('pic', 'cNvPicPr'))
    fill = ET.SubElement(pic, q('pic', 'blipFill'))
    ET.SubElement(fill, q('a', 'blip'), {q('r', 'embed'): 'rIdLogo'})
    stretch = ET.SubElement(fill, q('a', 'stretch'))
    ET.SubElement(stretch, q('a', 'fillRect'))
    sppr = ET.SubElement(pic, q('pic', 'spPr'))
    xfrm = ET.SubElement(sppr, q('a', 'xfrm'))
    ET.SubElement(xfrm, q('a', 'off'), {'x': '0', 'y': '0'})
    ET.SubElement(xfrm, q('a', 'ext'), {'cx': '1650000', 'cy': '510309'})
    geom = ET.SubElement(sppr, q('a', 'prstGeom'), {'prst': 'rect'})
    ET.SubElement(geom, q('a', 'avLst'))

    paragraph('ALIPEN SOLUTIONS AGENCY LTD', True, 28, BLUE)
    paragraph('Business address: [Insert verified business address] · Nairobi, Kenya', False, 16, GRAY)
    paragraph('INVOICE TEMPLATE', True, 36, NAVY)
    paragraph('Invoice number: [Enter invoice number]     Invoice date: [DD/MM/YYYY]     Due date: [DD/MM/YYYY]', True, 18, GRAY)
    paragraph('BILL TO', True, 20, BLUE)
    paragraph('Customer name: [Customer name]     Company / facility: [Company or facility]')
    paragraph('Address: [Customer address]')
    paragraph('Email: [Customer email]     Phone: [Customer phone]')

    def table(rows, widths=None):
        tbl = ET.SubElement(body, q('w', 'tbl'))
        props = ET.SubElement(tbl, q('w', 'tblPr'))
        borders = ET.SubElement(props, q('w', 'tblBorders'))
        for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
            ET.SubElement(borders, q('w', edge), {q('w', 'val'): 'single', q('w', 'sz'): '4', q('w', 'color'): 'C9D4E2'})
        for row_index, values in enumerate(rows):
            tr = ET.SubElement(tbl, q('w', 'tr'))
            for value in values:
                tc = ET.SubElement(tr, q('w', 'tc'))
                if row_index == 0:
                    tcpr = ET.SubElement(tc, q('w', 'tcPr'))
                    ET.SubElement(tcpr, q('w', 'shd'), {q('w', 'fill'): BLUE})
                p = ET.SubElement(tc, q('w', 'p'))
                r = ET.SubElement(p, q('w', 'r'))
                rpr = ET.SubElement(r, q('w', 'rPr'))
                ET.SubElement(rpr, q('w', 'color'), {q('w', 'val'): 'FFFFFF' if row_index == 0 else NAVY})
                ET.SubElement(rpr, q('w', 'sz'), {q('w', 'val'): '16'})
                if row_index == 0:
                    ET.SubElement(rpr, q('w', 'b'))
                ET.SubElement(r, q('w', 't')).text = value

    table([
        ['Item / product', 'Description / specifications', 'Qty', 'Unit price (KES)', 'Line total (KES)'],
        ['[Product or service]', '[Description]', '[0]', '[0.00]', '[0.00]'],
        ['[Product or service]', '[Description]', '[0]', '[0.00]', '[0.00]'],
        ['[Product or service]', '[Description]', '[0]', '[0.00]', '[0.00]'],
        ['[Product or service]', '[Description]', '[0]', '[0.00]', '[0.00]'],
    ])
    paragraph('Currency: KES [editable]')
    paragraph('Subtotal: KES [0.00]')
    paragraph('Discount (if applicable): KES [0.00 / N/A]')
    paragraph('Tax / VAT (if applicable): [Enter verified tax basis and amount, or N/A]')
    paragraph('TOTAL AMOUNT: KES [0.00]', True, 24, BLUE)
    paragraph('Amount paid: KES [0.00]     Balance due: KES [0.00]')
    paragraph('PAYMENT INSTRUCTIONS', True, 20, BLUE)
    paragraph('[Insert verified payment method, account details, and reference. Do not send until confirmed.]')
    paragraph('NOTES & TERMS', True, 20, BLUE)
    paragraph('[Add delivery, validity, warranty, and other agreed terms.]')
    paragraph('Authorized by: ______________________________    Name / title: [Authorized representative]')
    paragraph('Signature: __________________________________    Date: [DD/MM/YYYY]')
    paragraph('Nairobi, Kenya  |  +254 712 272 463  |  info@alipen.co.ke  |  alipen.co.ke', True, 16, GRAY, 'center')
    sect = ET.SubElement(body, q('w', 'sectPr'))
    ET.SubElement(sect, q('w', 'pgSz'), {q('w', 'w'): '11906', q('w', 'h'): '16838'})
    ET.SubElement(sect, q('w', 'pgMar'), {q('w', 'top'): '650', q('w', 'right'): '700', q('w', 'bottom'): '650', q('w', 'left'): '700'})

    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'''
    rels = '''<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rIdDoc" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'''
    doc_rels = '''<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rIdLogo" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/logo.png"/></Relationships>'''
    with ZipFile(OUT / 'alipen-invoice-template.docx', 'w', ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', content_types)
        archive.writestr('_rels/.rels', rels)
        archive.writestr('word/document.xml', ET.tostring(doc, encoding='utf-8', xml_declaration=True))
        archive.writestr('word/_rels/document.xml.rels', doc_rels)
        archive.write(LOGO, 'word/media/logo.png')


def decode_png_rgb(path):
    raw = path.read_bytes()
    if raw[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('Official logo must be PNG')
    offset, idat = 8, bytearray()
    while offset < len(raw):
        length = struct.unpack('>I', raw[offset:offset + 4])[0]
        kind = raw[offset + 4:offset + 8]
        data = raw[offset + 8:offset + 8 + length]
        if kind == b'IHDR':
            width, height, depth, color, comp, filt, interlace = struct.unpack('>IIBBBBB', data)
        elif kind == b'IDAT':
            idat.extend(data)
        elif kind == b'IEND':
            break
        offset += 12 + length
    if depth != 8 or color not in (2, 6) or interlace:
        raise ValueError('Logo PNG format must be 8-bit RGB or RGBA, non-interlaced')
    channels = 3 if color == 2 else 4
    scan = zlib.decompress(idat)
    stride = width * channels
    output, previous, cursor = bytearray(), bytearray(stride), 0
    for _ in range(height):
        mode = scan[cursor]
        row = bytearray(scan[cursor + 1:cursor + 1 + stride])
        cursor += stride + 1
        for i in range(stride):
            left = row[i - channels] if i >= channels else 0
            above = previous[i]
            upper_left = previous[i - channels] if i >= channels else 0
            if mode == 1: row[i] = (row[i] + left) & 255
            elif mode == 2: row[i] = (row[i] + above) & 255
            elif mode == 3: row[i] = (row[i] + ((left + above) // 2)) & 255
            elif mode == 4:
                p = left + above - upper_left
                pa, pb, pc = abs(p-left), abs(p-above), abs(p-upper_left)
                predictor = left if pa <= pb and pa <= pc else (above if pb <= pc else upper_left)
                row[i] = (row[i] + predictor) & 255
        if color == 2:
            output.extend(row)
        else:
            for i in range(0, stride, 4):
                a = row[i + 3]
                for c in range(3):
                    output.append((row[i + c] * a + 255 * (255 - a)) // 255)
        previous = row
    return width, height, bytes(output)


def pdf_string(value):
    value = value.encode('ascii', 'replace').decode('ascii')
    return '(' + value.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)') + ')'


def make_pdf():
    width, height, pixels = decode_png_rgb(LOGO)
    commands = []

    def text(x, y, value, size=9, color=(0.12, 0.18, 0.27), font='F1'):
        commands.append(f'{color[0]} {color[1]} {color[2]} rg BT /{font} {size} Tf {x} {y} Td {pdf_string(value)} Tj ET')

    def line(x1, y1, x2, y2, color=(0.78, 0.82, 0.87), weight=0.7):
        commands.append(f'{weight} w {color[0]} {color[1]} {color[2]} RG {x1} {y1} m {x2} {y2} l S')

    def rect(x, y, w, h, color):
        commands.append(f'{color[0]} {color[1]} {color[2]} rg {x} {y} {w} {h} re f')

    commands += ['q 100 0 0 31 42 794 cm /Logo Do Q']
    text(42, 765, 'ALIPEN SOLUTIONS AGENCY LTD', 12, (0.09, 0.32, 0.63), 'F2')
    text(422, 786, 'INVOICE TEMPLATE', 15, (0.07, 0.20, 0.36), 'F2')
    text(42, 747, 'Business address: [Insert verified business address] | Nairobi, Kenya', 8, (0.35, 0.40, 0.47))
    line(42, 738, 553, 738, (0.09, 0.32, 0.63), 2)
    text(42, 718, 'Invoice number: [Enter invoice number]')
    text(320, 718, 'Invoice date: [DD/MM/YYYY]')
    text(320, 701, 'Due date: [DD/MM/YYYY]')
    rect(42, 666, 511, 24, (0.92, 0.95, 0.98))
    text(51, 675, 'BILL TO', 9, (0.09, 0.32, 0.63), 'F2')
    text(51, 649, 'Customer name: [Customer name]')
    text(310, 649, 'Company / facility: [Company or facility]')
    text(51, 632, 'Address: [Customer address]')
    text(51, 615, 'Email: [Customer email]')
    text(310, 615, 'Phone: [Customer phone]')
    table_top, row_h = 580, 26
    columns = [42, 178, 350, 388, 470, 553]
    labels = ['Item / product', 'Description / specifications', 'Qty', 'Unit price', 'Line total']
    rect(42, table_top - row_h, 511, row_h, (0.09, 0.32, 0.63))
    for i, label in enumerate(labels): text(columns[i] + 5, table_top - 17, label, 7, (1, 1, 1), 'F2')
    for n in range(4):
        top = table_top - row_h * (n + 1)
        bottom = top - row_h
        line(42, bottom, 553, bottom)
        text(47, bottom + 9, '[Product / service]')
        text(183, bottom + 9, '[Description]')
        text(355, bottom + 9, '[0]')
        text(393, bottom + 9, '[0.00]')
        text(475, bottom + 9, '[0.00]')
    for x in columns: line(x, table_top, x, table_top - row_h * 5)
    totals_y = 422
    text(342, totals_y, 'Currency: KES [editable]')
    text(342, totals_y - 18, 'Subtotal: KES [0.00]')
    text(342, totals_y - 36, 'Discount: KES [0.00 / N/A]')
    text(342, totals_y - 54, 'Tax / VAT: [Verified basis and amount, or N/A]')
    rect(330, totals_y - 83, 223, 22, (0.92, 0.95, 0.98))
    text(339, totals_y - 75, 'TOTAL: KES [0.00]', 10, (0.09, 0.32, 0.63), 'F2')
    text(342, totals_y - 101, 'Amount paid: KES [0.00]')
    text(342, totals_y - 119, 'Balance due: KES [0.00]', 9, (0.07, 0.20, 0.36), 'F2')
    text(42, 418, 'PAYMENT INSTRUCTIONS', 9, (0.09, 0.32, 0.63), 'F2')
    text(42, 402, '[Insert verified payment method, account details, and reference.]', 8)
    text(42, 361, 'NOTES & TERMS', 9, (0.09, 0.32, 0.63), 'F2')
    text(42, 345, '[Add delivery, validity, warranty, and other agreed terms.]', 8)
    text(42, 267, 'Authorized by: _________________________     Name / title: [Authorized representative]', 8)
    text(42, 246, 'Signature: _____________________________     Date: [DD/MM/YYYY]', 8)
    line(42, 74, 553, 74, (0.78, 0.82, 0.87))
    text(42, 57, 'Nairobi, Kenya  |  +254 712 272 463  |  info@alipen.co.ke  |  alipen.co.ke', 8, (0.35, 0.40, 0.47))
    stream = ('\n'.join(commands)).encode('ascii')

    objects = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R /F2 5 0 R >> /XObject << /Logo 6 0 R >> >> /Contents 7 0 R >>',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>',
        (f'<< /Type /XObject /Subtype /Image /Width {width} /Height {height} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode /Length {len(zlib.compress(pixels))} >>\nstream\n'.encode('ascii') + zlib.compress(pixels) + b'\nendstream'),
        b'<< /Length ' + str(len(stream)).encode() + b' >>\nstream\n' + stream + b'\nendstream',
    ]
    pdf = bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf.extend(f'{number} 0 obj\n'.encode('ascii') + obj + b'\nendobj\n')
    xref = len(pdf)
    pdf.extend(f'xref\n0 {len(offsets)}\n'.encode('ascii'))
    pdf.extend(b'0000000000 65535 f \n')
    for offset in offsets[1:]: pdf.extend(f'{offset:010d} 00000 n \n'.encode('ascii'))
    pdf.extend(f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode('ascii'))
    (OUT / 'alipen-invoice-template.pdf').write_bytes(pdf)


if __name__ == '__main__':
    make_docx()
    make_pdf()
