"""Issue local demo credentials. Plaintext is printed once, never saved."""
import hashlib,json,secrets
from pathlib import Path
import argparse
p=argparse.ArgumentParser();p.add_argument('--root',default='runtime/news');args=p.parse_args()
root=Path(args.root);root.mkdir(parents=True,exist_ok=True)
target=root/'users.json'
if target.exists():raise SystemExit('users.json exists. Existing credentials preserved.')
users=[]
for name,role in [('writer','writer'),('editor','editor')]:
    token=secrets.token_urlsafe(24)
    users.append(dict(name=name,role=role,token_hash=hashlib.sha256(token.encode()).hexdigest()))
    print(f'{name}: {token}')
target.write_text(json.dumps(users),encoding='utf-8')
print('로컬 개발용 토큰입니다. 서로 다른 담당자에게 전달하고 외부 공개 서버에서 사용하지 마세요.')
