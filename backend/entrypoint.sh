#!/usr/bin/env sh
set -eu

python - <<'PYWAIT'
import os
import time
from sqlalchemy import create_engine, text

url = os.environ['DATABASE_URL']
for attempt in range(40):
    try:
        engine = create_engine(url, pool_pre_ping=True)
        with engine.connect() as connection:
            connection.execute(text('SELECT 1'))
        break
    except Exception as exc:
        if attempt == 39:
            raise
        print(f'PostgreSQL no esta listo ({exc}). Reintento {attempt + 1}/40...')
        time.sleep(2)
PYWAIT

alembic upgrade head

if [ "${SEED_ON_STARTUP:-true}" = "true" ]; then
    python -m app.seed
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
