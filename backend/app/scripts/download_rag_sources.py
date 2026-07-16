"""Download versioned official RAG sources without redistributing them.

The manifest is part of the repository. Raw files are downloaded at deployment
or demonstration time from the source organisation and accompanied by a JSON
sidecar containing their checksum and indexing metadata.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import get_settings

settings = get_settings()


def _load_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data.get('sources'), list):
        raise ValueError('El manifiesto no contiene una lista sources valida')
    return data


def _safe_filename(value: str) -> str:
    name = Path(value).name
    if not name or name != value or name in {'.', '..'}:
        raise ValueError(f'Nombre de fichero no valido: {value!r}')
    return name


def _validate_url(value: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme != 'https' or not parsed.netloc:
        raise ValueError(f'Solo se permiten URLs HTTPS: {value}')


def _download(client: httpx.Client, source: dict[str, Any], output_dir: Path, force: bool) -> dict[str, Any]:
    source_id = str(source['id'])
    url = str(source['url'])
    _validate_url(url)
    filename = _safe_filename(str(source['filename']))
    target = output_dir / filename
    sidecar = output_dir / f'{filename}.meta.json'

    if target.exists() and sidecar.exists() and not force:
        existing = json.loads(sidecar.read_text(encoding='utf-8'))
        return {
            'id': source_id,
            'status': 'skipped',
            'filename': filename,
            'sha256': existing.get('sha256'),
            'size_bytes': existing.get('size_bytes'),
        }

    with client.stream('GET', url) as response:
        response.raise_for_status()
        content_type = response.headers.get('content-type', '').split(';', 1)[0].strip().lower()
        expected_format = str(source.get('format', '')).lower()
        if expected_format == 'pdf' and content_type not in {'application/pdf', 'application/octet-stream'}:
            raise ValueError(f'{source_id}: se esperaba PDF y se recibio {content_type or "sin content-type"}')
        digest = hashlib.sha256()
        size = 0
        temporary = target.with_suffix(target.suffix + '.part')
        with temporary.open('wb') as stream:
            for chunk in response.iter_bytes(chunk_size=65_536):
                size += len(chunk)
                if size > settings.rag_source_max_bytes:
                    raise ValueError(
                        f'{source_id}: supera el maximo de {settings.rag_source_max_bytes} bytes'
                    )
                digest.update(chunk)
                stream.write(chunk)
        temporary.replace(target)

    metadata = {
        'schema_version': '1.0',
        'source_id': source_id,
        'download_url': url,
        'downloaded_at': datetime.now(timezone.utc).isoformat(),
        'content_type': content_type,
        'sha256': digest.hexdigest(),
        'size_bytes': size,
        'metadata': source.get('metadata') or {},
    }
    sidecar.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    return {
        'id': source_id,
        'status': 'downloaded',
        'filename': filename,
        'sha256': metadata['sha256'],
        'size_bytes': size,
    }


def run(manifest_path: Path, output_dir: Path, *, force: bool = False) -> dict[str, Any]:
    manifest = _load_manifest(manifest_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    headers = {
        'User-Agent': 'GamuCare-AI-academic-RAG/0.14 (+local MVP; source traceability)',
        'Accept': 'application/pdf,text/html,application/xhtml+xml;q=0.9,*/*;q=0.5',
    }
    with httpx.Client(follow_redirects=True, timeout=90.0, headers=headers) as client:
        for source in manifest['sources']:
            if not source.get('enabled', True):
                continue
            try:
                results.append(_download(client, source, output_dir, force))
            except Exception as exc:
                results.append({'id': source.get('id'), 'status': 'failed', 'error': str(exc)})

    summary = {
        'manifest': str(manifest_path),
        'output': str(output_dir),
        'downloaded': sum(item['status'] == 'downloaded' for item in results),
        'skipped': sum(item['status'] == 'skipped' for item in results),
        'failed': sum(item['status'] == 'failed' for item in results),
        'results': results,
    }
    (output_dir / 'download-report.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description='Descarga fuentes oficiales del RAG')
    parser.add_argument('--manifest', default=settings.rag_source_manifest)
    parser.add_argument('--output', default=settings.rag_external_documents_path)
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()
    summary = run(Path(args.manifest), Path(args.output), force=args.force)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if summary['failed'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
