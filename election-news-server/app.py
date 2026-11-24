import asyncio
import hashlib
import json
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import websockets
from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from core import Newsroom, now

ROOT=Path(os.environ.get('NEWS_DIR','runtime/news'))
room=Newsroom(ROOT)
connection=dict(state='CONNECTING',error=None,last_received_at=None,mode='unavailable')
UPSTREAM=os.environ.get('UPSTREAM_URL','http://127.0.0.1:8101')

def identity(authorization:str=Header(default='')):
    p=ROOT/'users.json'
    users=json.loads(p.read_text()) if p.exists() else []
    token=authorization.removeprefix('Bearer ')
    hashed=hashlib.sha256(token.encode()).hexdigest()
    user=next((u for u in users if secrets.compare_digest(u['token_hash'],hashed)),None)
    if not user:raise HTTPException(401,'로컬 사용자 토큰이 필요합니다')
    return user

def role(user,*roles):
    if user['role'] not in roles:raise HTTPException(403,'역할 권한이 없습니다')

def seed_demo_documents():
    for i,region in enumerate(['계양구을','연수구을','서구병']):
        for ci in range(2):
            room.add_document(dict(title=f'{region} 가상후보 {chr(65+ci)} 시뮬레이션 공약',publisher='VR 선거보도 시스템 가상 자료실',
                url='demo://fixtures/pledges',published_at='2024-04-01',collected_at='2026-11-20T00:00:00+09:00',
                document_type='campaign',election_id='KR-20240410-NA22',region_name=region,candidate_id=f'DEMO-{i}-{ci}',
                text=('교통 분야에서 환승 편의를 개선하겠다는 가상 공약이다. 추진 일정과 재원은 명시하지 않았다.' if ci==0 else '주거 분야에서 공공임대 상담을 확대하겠다는 가상 공약이다. 추진 일정과 재원은 명시하지 않았다.'),
                is_demo=True,rights='프로젝트 제작 가상 자료'), 'demo-bootstrap')

async def receive_loop():
    while True:
        try:
            # Catch-up before the streaming connection. Replays of duplicate events are idempotent.
            async with httpx.AsyncClient(timeout=5) as client:
                r=await client.get(UPSTREAM+'/events',params={'after':0});r.raise_for_status()
                for event in r.json():room.receive(event)
            async with websockets.connect(UPSTREAM.replace('http','ws',1)+'/ws?after=0',max_size=2**22) as ws:
                connection.update(state='CONNECTED',error=None)
                async for raw in ws:
                    event=json.loads(raw)
                    if event.get('type')=='heartbeat':continue
                    if room.receive(event):connection.update(last_received_at=now(),mode=event['mode'])
        except asyncio.CancelledError:raise
        except Exception as e:
            connection.update(state='DISCONNECTED',error=type(e).__name__+': '+str(e)[:180])
            if os.environ.get('ALLOW_DEMO_FALLBACK','1')=='1':
                # Separate, unmistakably labelled fixture, never relabel old official rows.
                sample=Path(__file__).with_name('fixtures')/'fallback_snapshot.json'
                if sample.exists():
                    event=json.loads(sample.read_text(encoding='utf-8'));event['fallback_at']=now()
                    room.receive(event);connection['mode']='demo'
            await asyncio.sleep(3)

@asynccontextmanager
async def lifespan(app):
    seed_demo_documents()
    task=asyncio.create_task(receive_loop())
    yield
    task.cancel()

app=FastAPI(title='VR 선거보도 시스템',lifespan=lifespan)
@app.get('/')
def home():return FileResponse(Path(__file__).with_name('index.html'))
@app.get('/health')
def health():return dict(status='ok',connection=connection,ai='UNAVAILABLE')
@app.get('/api/snapshot')
def snapshot():return dict(**room.latest(),connection=connection)
@app.get('/api/official-results')
def official_results():
    p=Path(__file__).with_name('reference_data')/'incheon_final_results.json'
    return dict(label='공식 파일 집계본 · 독립 검수 전 · 기사 생성에 자동 사용하지 않음',rows=json.loads(p.read_text(encoding='utf-8')) if p.exists() else [])
@app.websocket('/ws')
async def ws(websocket:WebSocket):
    await websocket.accept();last=None
    try:
        while True:
            result=dict(**room.latest(),connection=connection,screen_updated_at=now())
            value=json.dumps(result,ensure_ascii=False)
            if value!=last:await websocket.send_text(value);last=value
            await asyncio.sleep(1)
    except (WebSocketDisconnect,RuntimeError):pass
@app.get('/api/search')
def search(q:str,region:str,candidate:str):return room.search(q,region,candidate,demo=room.latest().get('mode')=='demo')

class Draft(BaseModel):region:str
@app.post('/api/articles')
def draft(req:Draft,user=Depends(identity)):
    role(user,'writer')
    try:return room.draft(req.region,user['name'])
    except ValueError as e:raise HTTPException(422,str(e))
@app.get('/api/articles')
def articles(user=Depends(identity)):
    return [json.loads(r[0]) for r in room.db.execute('SELECT payload FROM article ORDER BY rowid DESC')]
@app.get('/api/articles/{aid}')
def get(aid:str,user=Depends(identity)):
    try:return room.get(aid)
    except ValueError as e:raise HTTPException(404,str(e))
@app.post('/api/articles/{aid}/validate')
def validate(aid:str,user=Depends(identity)):
    try:return room.validate(room.get(aid),user['name'])
    except ValueError as e:raise HTTPException(404,str(e))
class Revision(BaseModel):
    title:str
    sentences:list[dict]
    reason:str=Field(min_length=5)
@app.post('/api/articles/{aid}/revisions')
def revision(aid:str,req:Revision,user=Depends(identity)):
    role(user,'writer')
    try:
        a=room.get(aid);old=a['id']
        a.update(id=secrets.token_hex(8),parent_id=old,revision=a['revision']+1,author=user['name'],title=req.title,sentences=req.sentences,status='DRAFT',created_at=now(),ai_review=dict(verdict='UNAVAILABLE',model=None))
        for key in ['validation','approved_by','approved_at','approval_reason']:a.pop(key,None)
        room.save(a);room.audit('revision',user['name'],dict(article_id=a['id'],parent_id=old,reason=req.reason));return a
    except ValueError as e:raise HTTPException(404,str(e))
class Approval(BaseModel):
    reason:str=Field(min_length=5)
    evidence_checked:bool
    ai_unavailable_ack:bool=False
@app.post('/api/articles/{aid}/approve')
def approve(aid:str,req:Approval,user=Depends(identity)):
    role(user,'editor')
    try:return room.approve(aid,user['name'],req.reason,req.evidence_checked,req.ai_unavailable_ack)
    except ValueError as e:raise HTTPException(409,str(e))
@app.get('/api/articles/{aid}/export')
def export(aid:str,user=Depends(identity)):
    role(user,'editor')
    try:return room.export(aid)
    except ValueError as e:raise HTTPException(409,str(e))
@app.post('/api/documents')
def document(doc:dict,user=Depends(identity)):
    role(user,'writer')
    try:return dict(chunk_ids=room.add_document(doc,user['name']))
    except ValueError as e:raise HTTPException(422,str(e))
@app.post('/api/chunks/{cid}/retire')
def retire(cid:str,user=Depends(identity)):
    role(user,'editor');room.retire(cid,user['name']);return dict(status='retired')
@app.get('/api/audit')
def audit(user=Depends(identity)):
    role(user,'editor');return [dict(id=r[0],previous_hash=r[1],hash=r[2],payload=json.loads(r[3])) for r in room.db.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 150')]
