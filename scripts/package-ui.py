"""Copy the freshly built public workbench into the Python package."""
from pathlib import Path
import json
import shutil

root = Path(__file__).resolve().parents[1]
build = root / 'ui' / 'dist'
target = root / 'valuation_agent' / 'web'
manifest = json.loads((build / 'assets' / 'current-build.json').read_text())
entry = manifest['entry'].lstrip('/')
if not entry.startswith('assets/') or '..' in Path(entry).parts or not (build / entry).is_file():
    raise ValueError('Invalid or missing UI build entry')
# Activation is maintained separately; replace only generated public assets.
shutil.rmtree(target / 'assets')
shutil.copytree(build / 'assets', target / 'assets')
for name in ('index.html', '报价单示例.xlsx'):
    shutil.copy2(build / name, target / name)
print('Packaged UI:', entry)
