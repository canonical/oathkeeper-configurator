# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.


from ops.model import ActiveStatus, BlockedStatus
from ops.testing import Harness

from tests.unit.conftest import (
    ACCESS_RULES_CONFIG,
    REMOTE_UNIT_NAME,
    SAMPLE_INGRESS_DATA,
    SAMPLE_URL,
    mock_ipu_relation_with_config,
)


def test_no_urls_set_on_config_changed(harness: Harness) -> None:
    """Test that the unit gets blocked when the required configs were not set."""
    harness.update_config()
    assert not harness.charm.access_rules_configured
    assert isinstance(harness.model.unit.status, BlockedStatus)


def test_on_config_changed(harness: Harness) -> None:
    """Test that the unit moves on to the next check when required configs were set."""
    harness.update_config({"access_rules": ACCESS_RULES_CONFIG, "root_url": SAMPLE_URL})
    assert harness.charm.access_rules_configured
    assert isinstance(harness.model.unit.status, BlockedStatus)
    assert harness.charm.unit.status == BlockedStatus(
        "Awaiting to be related via ingress-per-unit"
    )


def test_invalid_access_rules_config(harness: Harness) -> None:
    """Test access rules json validation."""
    harness.update_config({"access_rules": "some-invalid-config"})
    assert harness.charm.unit.status == BlockedStatus("Invalid json configuration, see logs")


def test_ingress_request_relaying_preconditions(harness: Harness) -> None:
    """Check that the charm gets blocked when the ipu relation is in place, but not ready."""
    harness.update_config({"access_rules": ACCESS_RULES_CONFIG, "root_url": SAMPLE_URL})

    _ = mock_ipu_relation_with_config(harness)
    assert harness.charm is not None  # for static checks

    assert harness.charm.unit.is_leader()
    assert (ipu_relation := harness.charm._ipu_relation)
    assert not harness.charm.ingress_per_unit.is_ready(ipu_relation)  # nothing's been shared yet
    assert harness.charm.unit.status == BlockedStatus("ingress-per-unit relation is not ready")


def test_on_ingress_request_called(harness: Harness) -> None:
    """Test that _on_ingress_data_provided is called on ipu relation change."""
    harness.update_config({"access_rules": ACCESS_RULES_CONFIG})
    ipu_relation_id = mock_ipu_relation_with_config(harness)

    assert harness.charm is not None  # for static checks
    harness.update_relation_data(ipu_relation_id, REMOTE_UNIT_NAME, SAMPLE_INGRESS_DATA)

    assert harness.charm.ingress_per_unit.is_ready(harness.charm._ipu_relation)
    assert isinstance(harness.charm.unit.status, ActiveStatus)
