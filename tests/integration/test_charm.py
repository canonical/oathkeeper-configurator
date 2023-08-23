#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.


import logging
from pathlib import Path
from typing import Dict

import pytest
import yaml
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)

METADATA = yaml.safe_load(Path("./metadata.yaml").read_text())
APP_NAME = METADATA["name"]
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
ROOT_URL = "http://foo.bar/{{juju_model}}-{{juju_unit}}"


@pytest.fixture
def config() -> Dict:
    return {
        "access_rules": ACCESS_RULES_CONFIG,
        "root_url": ROOT_URL,
    }


@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test: OpsTest, config: Dict) -> None:
    """Build and deploy the charm-under-test."""
    # build and deploy the charm from local source folder
    charm = await ops_test.build_charm(".")
    await ops_test.model.deploy(charm, application_name=APP_NAME, config=config, series="jammy")

    await ops_test.model.wait_for_idle(
        apps=[APP_NAME],
        timeout=600,
    )

    assert ops_test.model.applications[APP_NAME].units[0].workload_status == "blocked"
