"""Exercise new/unchanged/changed, row deletion and failure preservation."""
import shutil, tempfile, zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from ImportTool import run, NS, ROOT

def change_fixture(path):
    # Edit a temporary test copy only: remove one shift and adjust another's OT.
    with zipfile.ZipFile(path) as z: parts={n:z.read(n) for n in z.namelist()}
    name='xl/worksheets/sheet1.xml'; sheet=ET.fromstring(parts[name]); data=sheet.find(NS+'sheetData')
    data.remove(data.findall(NS+'row')[-1])
    cell=next(c for c in data.findall(NS+'row')[1] if c.get('r')=='I2');cell.find(NS+'v').text='3'
    parts[name]=ET.tostring(sheet)
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        for n,b in parts.items():z.writestr(n,b)

def main():
    with tempfile.TemporaryDirectory() as d:
        root=Path(d);shutil.copytree(ROOT/'raw',root/'raw')
        s,r=run(root);assert s['New']==2 and len(r)==12
        s,r=run(root);assert s['Unchanged']==2 and len(r)==12
        untouched=[x for x in r if x['SourceFile']=='WEO_2026-10-24.xlsx']
        p=root/'raw/WEO_2026-10-17.xlsx';change_fixture(p)
        s,r=run(root);assert s['Changed']==1 and s['Unchanged']==1 and len(r)==11
        assert [x for x in r if x['SourceFile']=='WEO_2026-10-24.xlsx']==untouched
        assert next(x for x in r if x['Shift ID']=='SHIFT-001-A')['Calculated Total']=='1025.00'
        s,r=run(root);assert s['Unchanged']==2 and len(r)==11
        before=(root/'output/state.json').read_bytes();p.write_bytes(b'bad workbook')
        try:run(root)
        except zipfile.BadZipFile:pass
        else:raise AssertionError('Invalid file accepted')
        assert (root/'output/state.json').read_bytes()==before
    print('PASS: new, unchanged, replacement, deletion, unaffected file, rerun, invalid workbook preserves state.')
if __name__=='__main__':main()
