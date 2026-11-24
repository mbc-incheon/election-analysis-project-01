"""Preserve exact public HTTP responses and a hash ledger, including failures."""
import concurrent.futures,hashlib,json
from datetime import datetime,timezone,timedelta
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'official_raw';OUT.mkdir(parents=True,exist_ok=True)
SOURCES=[
 ('NEC-RESULT-CATALOG','https://www.data.go.kr/data/15025527/fileData.do','중앙선거관리위원회 / 공공데이터포털','dataset_catalog'),
 ('NEC-RESULT-FILE','https://data.nec.go.kr/open-data/file.do?dataId=9','중앙선거관리위원회','download_index'),
 ('NEC-CAMPAIGN-LIBRARY','https://library.nec.go.kr/neweps/3/1/paper.do','중앙선거관리위원회','campaign_index'),
 ('NANET-IC-CAMPAIGN','https://dl.nanet.go.kr/detail/NONB12025000019286','국회도서관','campaign_catalog'),
]
def collect(item):
    sid,url,publisher,kind=item
    entry=dict(source_id=sid,url=url,publisher=publisher,kind=kind,collected_at=datetime.now(timezone(timedelta(hours=9))).isoformat(),published_at=None,baseline_at=None,status='FAILED',error=None,file_name=None)
    try:
        r=httpx.get(url,timeout=35,follow_redirects=True)
        entry.update(response_status=r.status_code,final_url=str(r.url),content_type=r.headers.get('content-type'))
        fn=f'{sid}_{hashlib.sha256(r.content).hexdigest()[:16]}.html';p=OUT/fn
        if not p.exists():p.write_bytes(r.content);p.chmod(0o444)
        entry.update(status='HTTP_CAPTURED' if r.is_success else 'HTTP_ERROR',file_name=fn,sha256=hashlib.sha256(r.content).hexdigest(),bytes=len(r.content))
        # These are landing pages. Do not pretend their contents are candidate or result records.
        entry.update(usable_as_result_rows=False,usable_as_candidate_pledge=False)
    except Exception as e:entry['error']=str(e)
    return entry
if __name__=='__main__':
    result=list(concurrent.futures.ThreadPoolExecutor(4).map(collect,SOURCES))
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S')
    target=ROOT/'data'/f'source_ledger_{stamp}.json'
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps([{k:r.get(k) for k in ['source_id','response_status','status','file_name','error']} for r in result],ensure_ascii=False))
