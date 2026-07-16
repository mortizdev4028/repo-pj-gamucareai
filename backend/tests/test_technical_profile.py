"""Regression tests for the isolated technical profile."""
from app.schemas import UserResponse
from app.services import system_evaluation


def test_user_schema_accepts_technical_role() -> None:
    schema = UserResponse.model_validate({
        'id': '11111111-1111-1111-1111-111111111111',
        'email': 'technical@example.test',
        'role': 'technical',
        'is_active': True,
        'must_change_password': False,
    })
    assert schema.role == 'technical'


def test_acceptance_requires_technical_role_source() -> None:
    source = system_evaluation.SystemEvaluator.evaluate_acceptance.__code__.co_consts
    assert any(isinstance(item, frozenset) and 'technical' in item for item in source)
