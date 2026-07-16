from app.services import observability


def test_dependency_status_ok(monkeypatch) -> None:
    monkeypatch.setattr(observability, '_check_postgres', lambda: None)
    monkeypatch.setattr(observability, '_check_http', lambda _: None)
    result = observability.dependency_status()
    assert result['status'] == 'ok'
    assert set(result['dependencies']) == {'postgres', 'qdrant', 'ollama'}
    assert all(item['status'] == 'up' for item in result['dependencies'].values())


def test_dependency_status_degraded(monkeypatch) -> None:
    monkeypatch.setattr(observability, '_check_postgres', lambda: None)

    def fail_ollama(url: str) -> None:
        if url.endswith('/api/tags'):
            raise RuntimeError('Ollama unavailable')

    monkeypatch.setattr(observability, '_check_http', fail_ollama)
    result = observability.dependency_status()
    assert result['status'] == 'degraded'
    assert result['dependencies']['ollama']['status'] == 'down'
    assert 'Ollama unavailable' in result['dependencies']['ollama']['error']
