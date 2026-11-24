import importlib.util,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for key,name in [('DATA_DIR','contracts_data'),('NEWS_DIR','contracts_news')]:os.environ[key]=str(ROOT/'build'/name)
for directory,label in [('election-data-server','data'),('election-news-server','news')]:
    sys.path.insert(0,str(ROOT/directory))
    spec=importlib.util.spec_from_file_location('contract_'+label,ROOT/directory/'app.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    (ROOT/'outputs'/f'openapi_{label}.json').write_text(json.dumps(mod.app.openapi(),ensure_ascii=False,indent=2),encoding='utf-8')
print('OpenAPI documents saved.')
