"""Stage and back up matching modules only; never restart services or edit data."""
import argparse, ast, datetime, pathlib, shutil, subprocess
p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('revision');p.add_argument('--source');a=p.parse_args()
root=pathlib.Path(a.root).resolve(); engine=root/'valuation_agent'/'_engine'
assert engine.is_dir(), 'Existing engine directory required'
files=('valuation_agent/_engine/workbench.py',
       'valuation_agent/_engine/quote_classification.py',
       'valuation_agent/_engine/valuation.py',
       'valuation_agent/source_identity.py',
       'valuation_agent/quote_library.py',
       'valuation_agent/server.py',
       'valuation_agent/excel_export.py')
backup=root.parent/('engine-backup-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
backup.mkdir()
staged={}
for name in files:
    url=f'https://raw.githubusercontent.com/yuguangtongchen1/valuation-agent/{a.revision}/{name}'
    payload=(pathlib.Path(a.source)/name).read_bytes() if a.source else subprocess.check_output(['curl','-fsSL','--retry','2','--max-time','45',url])
    ast.parse(payload,filename=name)
    staged[name]=payload
    target=root/name
    assert target.is_file(), f'Existing module required: {name}'
    (backup/name).parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(target,backup/name)
for name,payload in staged.items():
    target=root/name
    temp=target.with_suffix('.py.new');temp.write_bytes(payload);shutil.copymode(target,temp);temp.replace(target)
print('Updated matching, reference projection and Excel modules; backup:',backup)
