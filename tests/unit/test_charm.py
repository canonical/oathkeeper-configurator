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


def test_missing_config_on_config_changed(harness: Harness) -> None:
    """Test that the unit gets blocked when the required configs were not set.

    Note that config-changed is always emitted after on-install in events sequence.
    """
    harness.update_config()
    assert not harness.charm.access_rules_configured
    assert not harness.charm._is_traefik_config_ready
    assert isinstance(harness.model.unit.status, BlockedStatus)


def test_invalid_access_rules_config(harness: Harness) -> None:
    """Test that the unit gets blocked when the access_rules config is an invalid json."""
    harness.update_config({"access_rules": "some-invalid-config"})
    assert harness.charm.unit.status == BlockedStatus("Invalid json configuration, see logs")


def test_missing_traefik_config(harness: Harness) -> None:
    """Test that the unit gets blocked when root_url config is missing."""
    harness.update_config({"access_rules": ACCESS_RULES_CONFIG})
    assert harness.charm.unit.status == BlockedStatus(
        "Invalid or missing config. See logs for more info"
    )


def test_on_config_changed(harness: Harness) -> None:
    """Test that the unit moves on to the next check when required configs were set."""
    harness.update_config({"access_rules": ACCESS_RULES_CONFIG, "root_url": SAMPLE_URL})
    assert harness.charm.access_rules_configured
    assert harness.charm.unit.status == BlockedStatus(
        "Awaiting to be related via ingress-per-unit"
    )


def test_ingress_per_unit_relation_not_ready(harness: Harness) -> None:
    """Check that the charm gets blocked when the ipu relation is in place, but not ready."""
    harness.update_config({"access_rules": ACCESS_RULES_CONFIG, "root_url": SAMPLE_URL})

    _ = mock_ipu_relation_with_config(harness)
    assert harness.charm is not None  # for static checks

    assert harness.charm.unit.is_leader()
    assert (ipu_relation := harness.charm._ipu_relation)
    assert not harness.charm.ingress_per_unit.is_ready(ipu_relation)  # nothing's been shared yet
    assert harness.charm.unit.status == BlockedStatus("ingress-per-unit relation is not ready")


def test_configs_and_relations_set(harness: Harness) -> None:
    """Test the charm in scenario where all required configs/relations are set and valid.

    Check that _on_ingress_data_provided is called on ipu relation change.
    Ensure that the unit status gets active.
    """
    harness.update_config({"access_rules": ACCESS_RULES_CONFIG})
    ipu_relation_id = mock_ipu_relation_with_config(harness)

    assert harness.charm is not None  # for static checks
    harness.update_relation_data(ipu_relation_id, REMOTE_UNIT_NAME, SAMPLE_INGRESS_DATA)

    assert harness.charm._is_traefik_config_ready
    assert harness.charm.ingress_per_unit.is_ready(harness.charm._ipu_relation)
    assert isinstance(harness.charm.unit.status, ActiveStatus)
