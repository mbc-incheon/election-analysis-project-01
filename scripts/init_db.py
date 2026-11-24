"""Create a SQLite schema; optional fixtures are restricted to empty project databases."""
import argparse
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLES = ('snapshot', 'chunk', 'article', 'approval', 'audit')


def initialize(path, demo=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.execute('PRAGMA foreign_keys=ON')
        existing = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if demo and existing:
            if existing - set(TABLES) - {'sqlite_sequence'}:
                raise ValueError('Unrecognized database: demo seed refused')
            if any(db.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
                   for name in TABLES if name in existing):
                raise ValueError('Database contains records; demo seed refused. Choose a new path.')
        db.executescript((ROOT / 'db/001_schema.sql').read_text(encoding='utf-8'))
        if demo:
            db.executescript((ROOT / 'db/002_demo_seed.sql').read_text(encoding='utf-8'))
        if list(db.execute('PRAGMA foreign_key_check')):
            raise ValueError('Foreign key validation failed')
        return {t: db.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in TABLES}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--path', default=str(ROOT / 'runtime/news/news.sqlite'))
    parser.add_argument('--demo', action='store_true')
    args = parser.parse_args()
    try:
        counts = initialize(args.path, args.demo)
    except ValueError as exc:
        parser.exit(2, str(exc) + '\n')
    print('Database:', args.path)
    print(counts)
    if args.demo:
        print('시뮬레이션 데이터입니다. 실제 승인 기록은 없으며 모든 기사는 DRAFT입니다.')


if __name__ == '__main__':
    main()
