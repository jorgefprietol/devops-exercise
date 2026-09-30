import glob
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

files = glob.glob('evidence/green/**/coverage.cobertura.xml', recursive=True)
if not files:
    raise SystemExit('Missing coverage report')
root = ET.parse(max(files, key=lambda p: Path(p).stat().st_mtime)).getroot()
rate = float(root.attrib['line-rate']) * 100
branch = float(root.attrib['branch-rate']) * 100
print(f'Line coverage: {rate:.2f}% | Branch coverage: {branch:.2f}%')
if rate < float(sys.argv[1] if len(sys.argv) > 1 else 80):
    raise SystemExit('Coverage below the required threshold')
