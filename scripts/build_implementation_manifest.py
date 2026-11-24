"""Record exact deliverable bytes and source provenance without local secrets."""
import argparse
import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(*args, cwd=ROOT):
    return subprocess.check_output(['git', *args], cwd=cwd).decode('utf-8').strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', type=Path)
    args = parser.parse_args()
    names = set(subprocess.check_output(
        ['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT
    ).decode('utf-8').split('\0'))
    records = []
    for name in sorted(names):
        if not name or name == 'outputs/implementation_manifest.json':
            continue
        file = ROOT / name
        if file.is_file():
            content = file.read_bytes()
            records.append(dict(path=name, bytes=len(content), sha256=hashlib.sha256(content).hexdigest()))
    result = dict(
        captured_at=datetime.now(timezone(timedelta(hours=9))).isoformat(),
        repository='https://github.com/mbc-incheon/election-analysis-project-01',
        repository_base_commit=git('rev-parse', 'HEAD'),
        note='Base commit is the parent context before this manifest is committed; exact publication commit is in Git history.',
        runtime=dict(python=platform.python_version()), files=records,
        editorial_approval='NOT_CREATED_BY_THIS_MANIFEST')
    if args.source_root:
        result['source'] = dict(
            repository='https://github.com/mbc-incheon/Real-time-Election-News',
            base_commit=git('rev-parse', 'HEAD', cwd=args.source_root),
            working_tree_modifications=git('diff','--name-only',cwd=args.source_root).splitlines(),
            note='Local modified snapshot integrated; original working tree preserved.')
    (ROOT / 'outputs/implementation_manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Manifest records:', len(records))


if __name__ == '__main__':
    main()
