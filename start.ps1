$ErrorActionPreference='Stop'
Set-Location $PSScriptRoot
$pythonPath=Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if(-not (Test-Path $pythonPath)){throw 'README의 설치 단계에 따라 .venv를 먼저 만드세요.'}
$env:DATA_DIR=Join-Path $PSScriptRoot 'runtime/data'
$env:NEWS_DIR=Join-Path $PSScriptRoot 'runtime/news'
$env:UPSTREAM_URL='http://127.0.0.1:8101'
if(-not (Test-Path (Join-Path $env:NEWS_DIR 'users.json'))){& $pythonPath scripts/init_users.py}
$producer=Start-Process -FilePath $pythonPath -ArgumentList '-m','uvicorn','app:app','--app-dir','election-data-server','--host','127.0.0.1','--port','8101' -WindowStyle Hidden -PassThru
try { & $pythonPath -m uvicorn app:app --app-dir election-news-server --host 127.0.0.1 --port 8102 }
finally { if(-not $producer.HasExited){Stop-Process -Id $producer.Id} }
