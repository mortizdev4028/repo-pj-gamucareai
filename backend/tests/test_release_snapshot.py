from app.scripts.release_snapshot import _json_default
from app.version import APP_VERSION


def test_release_candidate_version_is_exposed():
    assert APP_VERSION == '0.16.0-rc1'


def test_release_snapshot_json_fallback_is_stable():
    class Value:
        def __str__(self) -> str:
            return 'snapshot-value'

    assert _json_default(Value()) == 'snapshot-value'
