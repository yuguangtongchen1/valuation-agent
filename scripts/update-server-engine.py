"""Stage and back up matching modules only; never restart services or edit data."""
import argparse, ast, datetime, pathlib, shutil, urllib.request
p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('revision');a=p.parse_args()
root=pathlib.Path(a.root).resolve(); engine=root/'valuation_agent'/'_engine'
assert engine.is_dir(), 'Existing engine directory required'
files=('workbench.py','quote_classification.py')
backup=root.parent/('engine-backup-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
backup.mkdir()
staged={}
for name in files:
    url=f'https://raw.githubusercontent.com/yuguangtongchen1/valuation-agent/{a.revision}/valuation_agent/_engine/{name}'
    payload=urllib.request.urlopen(url,timeout=45).read()
    ast.parse(payload,filename=name)
    staged[name]=payload
    shutil.copy2(engine/name,backup/name)
for name,payload in staged.items():
    temp=engine/(name+'.new');temp.write_bytes(payload);shutil.copymode(engine/name,temp);temp.replace(engine/name)
print('Updated only matching modules; backup:',backup)
