# election-news-server

개표 수신, 공약 근거 검색, 정형 기사 생성, 규칙 검증과 독립 편집 승인을 제공하는 로컬 개발용 서버입니다. 외부 생성형 AI·벡터 DB는 연결하지 않았습니다. 실제 후보 공약 본문 대조와 사람 승인은 별도입니다.

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe init_users.py
.venv/Scripts/python.exe -m uvicorn app:app --host 127.0.0.1 --port 8102
```

먼저 데이터 서버를 8101번 포트로 실행합니다. 주소를 바꾸면 `UPSTREAM_URL`에 지정합니다. [http://127.0.0.1:8102](http://127.0.0.1:8102)에서 화면을 엽니다. 최초 토큰은 한 번만 표시합니다. writer와 editor는 서로 다른 실제 담당자가 사용하세요. `.env.example`은 참고용이며 자동으로 읽지 않습니다.

WebSocket 수신 실패 시 `fixtures/fallback_snapshot.json`의 시뮬레이션 자료로 대체합니다. `/api/official-results`는 공식 CSV의 별도 집계 자료실이며 독립 검수 전 자동 기사 입력에서 제외합니다. API 문서는 `/docs`입니다.

작성자 권한으로 최종 승인할 수 없습니다. 규칙 실패 또는 보조 판정 불일치는 서버에서 승인을 거부합니다. AI가 미연결인 상태에서 editor는 원문을 직접 대조하고 사유를 기록해야 합니다. 자동 시험 승인 기록을 실제 편집 승인으로 제출하지 마세요. 실제 운영 배포 전 인증·백업·접속 제한 검토가 필요합니다.
