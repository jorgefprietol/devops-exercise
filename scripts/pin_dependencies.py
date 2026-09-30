"""Maintainer helper: replace floating requested versions with resolved lock versions."""
import json
from pathlib import Path
import re

for path in Path('.').rglob('*.csproj'):
    versions = json.loads((path.parent / 'packages.lock.json').read_text())['dependencies']['net8.0']
    source = re.sub(r'(<PackageReference Include="([^"]+)" Version=")([^"]+)',
                    lambda m: m[1] + versions[m[2]]['resolved'], path.read_text(encoding='utf-8-sig'))
    path.write_text(source, encoding='utf-8')
