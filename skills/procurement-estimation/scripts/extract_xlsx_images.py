"""Extract embedded XLSX images with sheet/anchor evidence; no visual inference."""
import argparse
import json
import posixpath
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
      'x': 'http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing',
      'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}

def relationships(z, part):
    name = posixpath.join(posixpath.dirname(part), '_rels', posixpath.basename(part) + '.rels')
    if name not in z.namelist():
        return {}
    return {r.get('Id'): (r.get('Target').lstrip('/') if r.get('Target').startswith('/')
            else posixpath.normpath(posixpath.join(posixpath.dirname(part), r.get('Target'))))
            for r in ET.fromstring(z.read(name)) if r.get('TargetMode') != 'External'}

def extract(source, output, sheets=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    records = []
    with zipfile.ZipFile(source) as z:
        book = 'xl/workbook.xml'
        parts = relationships(z, book)
        for sheet in ET.fromstring(z.read(book)).findall('s:sheets/s:sheet', NS):
            if sheets and sheet.get('name') not in sheets:
                continue
            part = parts[sheet.get('{%s}id' % REL)]
            drawings = relationships(z, part)
            for drawing in ET.fromstring(z.read(part)).findall('s:drawing', NS):
                dpart = drawings[drawing.get('{%s}id' % REL)]
                media = relationships(z, dpart)
                for anchor in ET.fromstring(z.read(dpart)):
                    for blip in anchor.findall('.//a:blip', NS):
                        target = media.get(blip.get('{%s}embed' % REL))
                        if not target:
                            continue
                        name = 'image_%04d%s' % (len(records) + 1, Path(target).suffix)
                        (output / name).write_bytes(z.read(target))
                        def position(tag):
                            node = anchor.find('x:' + tag, NS)
                            if node is None:
                                return None
                            return {k: int(node.find('x:' + k, NS).text) + 1 for k in ('row', 'col')}
                        records.append({'sheet': sheet.get('name'), 'anchor_start': position('from'),
                                        'anchor_end': position('to'), 'image': name,
                                        'source_part': target, 'association_status': 'needs_visual_review'})
    (output / 'index.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
    return records

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source')
    p.add_argument('--out', required=True)
    p.add_argument('--sheet', action='append', help='Exact worksheet name; repeat for several sheets')
    a = p.parse_args()
    print(json.dumps({'images': len(extract(a.source, a.out, a.sheet)), 'index': str(Path(a.out) / 'index.json')}))
