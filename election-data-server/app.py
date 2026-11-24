"""Local teaching service. Historical election, synthetic replay, never a live result."""
import asyncio
import hashlib
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Header, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

ROOT = Path(os.environ.get('DATA_DIR', 'runtime/data'))
KST = timezone(timedelta(hours=9))
def now(): return datetime.now(KST).isoformat()
def digest(data): return hashlib.sha256(data).hexdigest()

class Store:
    def __init__(self, root):
        self.root = Path(root)
        (self.root / 'raw').mkdir(parents=True, exist_ok=True)
        (self.root / 'clean').mkdir(exist_ok=True)
        self.events = []
        self.error = None
        for p in sorted((self.root/'clean').glob('*.json')):
            self.events.append(json.loads(p.read_text(encoding='utf-8')))

    def append(self, payload, url, status=200):
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
        seq = len(self.events)+1
        stamp = now()
        raw = self.root/'raw'/f'{seq:08d}_{digest(body)[:12]}.json'
        with raw.open('xb') as f: f.write(body)
        raw.chmod(0o444)
        ledger = dict(sequence=seq, url=url, collected_at=stamp, response_status=status,
                      raw_file=str(raw), sha256=digest(body), mode=payload['mode'])
        with (self.root/'ledger.jsonl').open('a', encoding='utf-8') as f:
            f.write(json.dumps(ledger, ensure_ascii=False)+'\n')
        event = dict(sequence=seq, collected_at=stamp, **payload)
        (self.root/'clean'/f'{seq:08d}.json').write_text(json.dumps(event,ensure_ascii=False,indent=2),encoding='utf-8')
        self.events.append(event)
        return event

    def demo(self):
        n = len(self.events)
        progress = [30,60,90,100][n%4]
        rows=[]
        # This fixture is entirely invented. No actual candidate names or party labels.
        for ri, region in enumerate(['계양구을','연수구을','서구병']):
            votes = [int(progress*317+ri*23),int(progress*293+ri*17)]
            for ci, v in enumerate(votes):
                rows.append(dict(row_id=f'DEMO-{n+1}-{ri}-{ci}', election_id='KR-20240410-NA22',
                    region_id=f'DEMO-IC-{ri}', region_name=region, original_region_name='인천광역시 '+region,
                    candidate_id=f'DEMO-{ri}-{ci}', candidate_name=f'가상후보 {chr(65+ci)}', votes=v,
                    valid_votes=sum(votes), vote_share=round(v/sum(votes)*100,2),
                    counted_ballots=progress*1000, total_ballots=100000, count_rate=progress,
                    turnout=None, baseline_at=f'2024-04-10T{20+n%4:02d}:00:00+09:00',
                    source_url='demo://fixtures/ballots', is_demo=True))
        return self.append(dict(mode='demo',label='시뮬레이션 데이터',election_id='KR-20240410-NA22',
            historical_replay=True, rows=rows), 'demo://fixtures/ballots')

def validate_official(payload):
    if payload.get('mode')!='official': raise ValueError('mode must be official')
    rows=payload.get('rows',[])
    if not rows: raise ValueError('empty rows')
    groups={}
    for r in rows:
        if r.get('is_demo') is not False: raise ValueError('official rows require is_demo=false')
        if r['election_id']!='KR-20240410-NA22': raise ValueError('wrong election')
        if not r['source_url'].startswith(('https://info.nec.go.kr/','https://data.nec.go.kr/','https://www.data.go.kr/')):
            raise ValueError('official source required')
        if not all(r.get(x) for x in ['row_id','candidate_id','candidate_name','region_id','region_name']): raise ValueError('missing identity')
        t=datetime.fromisoformat(r['baseline_at'])
        if t.tzinfo is None or t.year!=2024: raise ValueError('historical timezone required')
        if type(r['votes']) is not int or r['votes']<0 or r['valid_votes']<=0: raise ValueError('invalid votes')
        if abs(r['votes']/r['valid_votes']*100-r['vote_share'])>0.011: raise ValueError('share mismatch')
        if not 0<=r['count_rate']<=100: raise ValueError('invalid count rate')
        groups.setdefault(r['region_id'],[]).append(r)
    if len({r['row_id'] for r in rows})!=len(rows): raise ValueError('duplicate row id')
    for group in groups.values():
        if len({r['candidate_id'] for r in group})!=len(group): raise ValueError('duplicate candidate')
        if len({(r['valid_votes'],r['baseline_at'],r['count_rate']) for r in group})!=1: raise ValueError('mixed group')
        if sum(r['votes'] for r in group)!=group[0]['valid_votes']: raise ValueError('incomplete candidates')
    return payload

store=Store(ROOT)
async def clock_loop():
    while True:
        if os.environ.get('DATA_MODE','demo')=='demo': store.demo()
        await asyncio.sleep(float(os.environ.get('DATA_INTERVAL','4')))

@asynccontextmanager
async def lifespan(app):
    task=asyncio.create_task(clock_loop())
    yield
    task.cancel()

app=FastAPI(title='VR 선거보도 시스템 · 데이터 송신',lifespan=lifespan)
@app.get('/health')
def health(): return dict(status='ok',mode=os.environ.get('DATA_MODE','demo'),error=store.error)
@app.get('/snapshot')
def snapshot(): return store.events[-1] if store.events else dict(sequence=0,mode='unavailable',rows=[])
@app.get('/events')
def events(after:int=0): return [e for e in store.events if e['sequence']>after]
@app.post('/ingest')
def ingest(payload:dict,authorization:str=Header(default='')):
    token=os.environ.get('INGEST_TOKEN')
    if not token or authorization!='Bearer '+token: raise HTTPException(401,'ingest token required')
    try: validate_official(payload)
    except (ValueError,KeyError,TypeError) as e: raise HTTPException(422,str(e))
    return store.append(payload,payload['rows'][0]['source_url'])
@app.websocket('/ws')
async def ws(websocket:WebSocket,after:int=0):
    await websocket.accept()
    try:
        while True:
            pending=[e for e in store.events if e['sequence']>after]
            for e in pending:
                await websocket.send_json(e); after=e['sequence']
            if not pending: await websocket.send_json(dict(type='heartbeat',server_at=now()))
            await asyncio.sleep(1)
    except (WebSocketDisconnect,RuntimeError): pass
