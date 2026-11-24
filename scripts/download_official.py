import hashlib,json
from datetime import datetime,timezone,timedelta
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1]
url='https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId=FILE_000000003172714&fileDetailSn=1'
r=httpx.get(url,follow_redirects=True,timeout=60);r.raise_for_status()
if len(r.content)<5000 or b'<html' in r.content[:500].lower():raise ValueError('Not a valid result file')
p=ROOT/'data'/'official_raw'/'NEC_NA22_20240410.csv'
if not p.exists():p.write_bytes(r.content);p.chmod(0o444)
ledger=dict(source_id='NEC-NA22-CSV',url=url,catalog_url='https://www.data.go.kr/data/15025527/fileData.do',publisher='중앙선거관리위원회',collected_at=datetime.now(timezone(timedelta(hours=9))).isoformat(),response_status=r.status_code,file_name=p.name,sha256=hashlib.sha256(r.content).hexdigest(),bytes=len(r.content),rights='공공누리 제1유형 출처표시',election_date='2024-04-10',baseline_at=None,note='최종 개표결과 파일. 실시간 단계별 시각은 제공하지 않음')
(ROOT/'data'/'official_csv_ledger.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(ledger,ensure_ascii=False))
