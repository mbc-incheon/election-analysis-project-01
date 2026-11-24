# election-data-server

2024년 총선 인천 시뮬레이션 개표 데이터 송신 서버입니다. 기본값은 가상후보·가상 수치입니다. 실제 현재 개표 데이터로 사용하지 않습니다.

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m uvicorn app:app --host 127.0.0.1 --port 8101
```

`/snapshot`, `/events?after=0`, WebSocket `/ws?after=0`를 제공합니다. 원본은 `runtime/data/raw`, 정제 이벤트는 `runtime/data/clean`, 원장은 `ledger.jsonl`에 저장합니다. `DATA_MODE=official`이면 가상 갱신을 멈추고 토큰이 있는 `/ingest`만 받습니다. 환경변수 예시는 `.env.example`이며 자동으로 읽지는 않습니다.

공식 결과 파일의 정확한 개표 기준시각이 없으면 임의로 입력하지 마세요. 해당 파일은 보도 서버 자료실의 검수 대기 집계본으로만 사용합니다. API 문서는 `/docs`에 있습니다. 로컬 개발용 서버이며 외부 인증과 TLS 배포는 별도 작업입니다.
