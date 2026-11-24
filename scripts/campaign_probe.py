import httpx,re,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
with httpx.Client(timeout=25,follow_redirects=True) as c:
    base='https://library.nec.go.kr/neweps/3/1/paper.do'
    r=c.get(base)
    text=r.content.decode('cp949')
    fields=dict(re.findall(r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"',text))
    fields.update(elecType='20',elecTypeMax='30',elecDe='국회의원선거',page='1',chs='')
    r=c.post('https://library.nec.go.kr/neweps/3/1/paperSearch.do',data=fields,headers={'Referer':base,'Origin':'https://library.nec.go.kr'})
    (ROOT/'build/campaign_probe.html').write_bytes(r.content)
    print(r.status_code,len(r.content))
    (ROOT/'build/campaign_fields.json').write_text(json.dumps(fields,ensure_ascii=False,indent=2),encoding='utf-8')
