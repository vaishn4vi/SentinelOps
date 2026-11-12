import pytest

from app.validators import ValidationError, normalize_status, validate_deployment_payload


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("success", "success"),
        ("SUCCESS", "success"),
        ("passed", "success"),
        ("failure", "failed"),
        ("rolled back", "rolled_back"),
        ("rollback", "rolled_back"),
        ("running", "in_progress"),
    ],
)
def test_normalize_status(raw, expected):
    assert normalize_status(raw) == expected


def test_valid_payload_defaults(deployment_payload):
    data = validate_deployment_payload(deployment_payload)
    assert data["environment"] == "production"
    assert data["triggered_by"] == "jenkins"
    assert data["duration_seconds"] is None
    assert data["build_number"] == 42


def test_build_number_as_string(deployment_payload):
    deployment_payload["build_number"] = " 17 "
    assert validate_deployment_payload(deployment_payload)["build_number"] == 17


def test_negative_build_number_rejected(deployment_payload):
    deployment_payload["build_number"] = -1
    with pytest.raises(ValidationError) as exc:
        validate_deployment_payload(deployment_payload)
    assert "build_number" in exc.value.errors


def test_invalid_commit_and_service_name(deployment_payload):
    deployment_payload["commit_id"] = "not a sha!"
    deployment_payload["service_name"] = "bad name with spaces"
    with pytest.raises(ValidationError) as exc:
        validate_deployment_payload(deployment_payload)
    assert {"commit_id", "service_name"} <= set(exc.value.errors)


def test_optional_fields(deployment_payload):
    deployment_payload.update(environment="Staging", duration_seconds="93.7", notes="ok")
    data = validate_deployment_payload(deployment_payload)
    assert data["environment"] == "staging"
    assert data["duration_seconds"] == 93
    assert data["notes"] == "ok"
