"""Tests for external corpus metadata and text extraction."""
from __future__ import annotations

import json
from pathlib import Path

from app.rag.ingest import parse_document


def test_external_html_uses_sidecar_metadata(tmp_path: Path) -> None:
    document = tmp_path / 'official.html'
    document.write_text(
        '<html><head><style>.hidden{display:none}</style></head>'
        '<body><h1>Guia veterinaria</h1><script>ignored()</script><p>Vacunacion canina.</p></body></html>',
        encoding='utf-8',
    )
    sidecar = tmp_path / 'official.html.meta.json'
    sidecar.write_text(
        json.dumps({'metadata': {'title': 'Guia oficial', 'source': 'Organismo'}}),
        encoding='utf-8',
    )

    metadata, text = parse_document(document)

    assert metadata['title'] == 'Guia oficial'
    assert metadata['source'] == 'Organismo'
    assert 'Guia veterinaria' in text
    assert 'Vacunacion canina' in text
    assert 'ignored' not in text


def test_markdown_front_matter_remains_supported(tmp_path: Path) -> None:
    document = tmp_path / 'guide.md'
    document.write_text(
        '---\ntitle: Guia local\nsource: Fuente de prueba\n---\n# Vacunas\nContenido.',
        encoding='utf-8',
    )
    metadata, text = parse_document(document)
    assert metadata['title'] == 'Guia local'
    assert text.startswith('# Vacunas')
