"""Test incremental imports in one persistent temporary workspace."""
import shutil, tempfile, zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from ImportTool import run, read_rows, NS, ROOT


def delete_one_shift(path):
    # Test fixture only. Remove a row from a source timesheet, not its invoice tab.
    with zipfile.ZipFile(path) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    name = 'xl/worksheets/sheet1.xml'
    sheet = ET.fromstring(parts[name])
    data = sheet.find(NS + 'sheetData')
    rows = data.findall(NS + 'row')
    assert len(rows) > 1
    data.remove(rows[-1])
    parts[name] = ET.tostring(sheet)
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        for n, b in parts.items():
            z.writestr(n, b)


def main():
    sources = sorted((ROOT / 'raw').glob('*.xlsx'))
    assert len(sources) >= 2
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / 'raw').mkdir()
        shutil.copytree(ROOT / 'mapping', root / 'mapping')
        for p in sources[:-1]:
            shutil.copy2(p, root / 'raw' / p.name)
        initial = sum(len(read_rows(p)) for p in sources[:-1])
        s, r = run(root)
        assert s['New'] == len(sources) - 1 and len(r) == initial
        s, r = run(root)
        assert s['Unchanged'] == len(sources) - 1 and len(r) == initial
        print(f'PASS: initial import and unchanged rerun: {initial} rows')
        added = sources[-1]
        shutil.copy2(added, root / 'raw' / added.name)
        total = initial + len(read_rows(added))
        s, r = run(root)
        assert s['New'] == 1 and s['Unchanged'] == len(sources)-1 and len(r) == total
        print(f'PASS: add {added.name}: {initial} -> {total} rows')
        p = root / 'raw' / sources[0].name
        before = {x['Shift ID']: x for x in r}
        untouched = [x for x in r if x['SourceFile'] != p.name]
        delete_one_shift(p)
        s, r = run(root)
        assert s['Changed'] == 1 and s['Unchanged'] == len(sources)-1 and len(r) == total-1
        after = {x['Shift ID']: x for x in r}
        removed = set(before) - set(after)
        assert len(removed) == 1 and not (set(after) - set(before))
        assert [x for x in r if x['SourceFile'] != p.name] == untouched
        print(f'PASS: replace {p.name}, remove {removed.pop()}: {total} -> {total-1} rows; other files unchanged')
        s, r = run(root)
        assert s['Unchanged'] == len(sources) and len(r) == total-1
        state = (root / 'output/state.json').read_bytes()
        p.write_bytes(b'bad workbook')
        try:
            run(root)
        except zipfile.BadZipFile:
            pass
        else:
            raise AssertionError('Invalid file accepted')
        assert (root / 'output/state.json').read_bytes() == state
        print('PASS: unchanged rerun, invalid workbook preserves prior state')

if __name__ == '__main__':
    main()
