# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

from typing import Generator

import pytest
from ops.testing import Harness

from charm import OathkeeperConfiguratorCharm

MODEL_NAME = "testing"
REMOTE_APP_NAME = "remote"  # the app requesting ingress
REMOTE_UNIT_NAME = f"{REMOTE_APP_NAME}/0"  # the unit requesting ingress
TRAEFIK_APP_NAME = "traefik"  # the app providing ingress
TRAEFIK_UNIT_NAME = f"{TRAEFIK_APP_NAME}/0"  # the unit providing ingress
SAMPLE_RULE = "Host(`foo.bar/{{juju_model}}-{{juju_unit}}`)"
SAMPLE_URL = "http://foo.bar/{{juju_model}}-{{juju_unit}}"
SAMPLE_CONFIG = {"rule": SAMPLE_RULE, "root_url": SAMPLE_URL}
SAMPLE_INGRESS_DATA = {"model": MODEL_NAME, "name": REMOTE_UNIT_NAME, "host": "foo", "port": "42"}
ACCESS_RULES_CONFIG = """
{
    "id": "some-id",
    "version": "v0.1",
    "match": {
        "url": "http://test-app/some-route/<.*>",
        "methods": ["GET", "POST"]
    },
    "authenticators": [{"handler": "noop"}],
    "authorizer": {"handler": "allow"},
    "mutators": [{"handler": "noop"}],
    "errors": [{"handler": "json"}]
}
"""


@pytest.fixture()
def harness() -> Generator[Harness, None, None]:
    harness = Harness(OathkeeperConfiguratorCharm)
    harness.set_model_name(MODEL_NAME)
    harness.set_leader(True)
    harness.begin()
    yield harness
    harness.cleanup()


def mock_config(harness: Harness) -> None:
    harness.update_config(SAMPLE_CONFIG)


def mock_ipu_relation(harness: Harness) -> int:
    ipu_relation_id = harness.add_relation(
        OathkeeperConfiguratorCharm._ingress_relation_name, REMOTE_APP_NAME
    )
    harness.add_relation_unit(ipu_relation_id, REMOTE_UNIT_NAME)
    return ipu_relation_id


def mock_ipu_relation_with_config(harness: Harness) -> int:
    ipu_relation_id = mock_ipu_relation(harness)
    mock_config(harness)

    return ipu_relation_id
