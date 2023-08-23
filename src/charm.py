#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""A Juju charm for configuring Charmed Ory Oathkeeper with downstream applications."""

import json
import logging
import textwrap
from dataclasses import dataclass
from itertools import starmap
from typing import Any, Iterable, Optional, Tuple
from urllib.parse import urlparse

import jinja2
from charms.traefik_k8s.v1.ingress_per_unit import (
    IngressDataReadyEvent,
    IngressPerUnitProvider,
    RequirerData,
)
from ops.charm import CharmBase, ConfigChangedEvent, EventBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus, Relation, Unit

from types_ import TraefikConfig, UnitConfig

logger = logging.getLogger(__name__)


class InvalidConfigError(Exception):
    """Internal exception that is raised if the charm config is not valid."""


class RuleDerivationError(RuntimeError):
    """Raised when a rule cannot be derived from other config parameters.

    Solution: provide the rule manually, or fix what's broken.
    """

    def __init__(self, url: str, *args):
        msg = f"Unable to derive Rule from {url!r}; ensure that the url is valid."
        super().__init__(msg, *args)


class TemplateKeyError(RuntimeError):
    """Raised when a template contains a key which we cannot provide.

    Solution: fix the template to only include the variables:
        - `juju_model`
        - `juju_application`
        - `juju_unit`
    """

    def __init__(self, template: str, key: str, *args):
        msg = textwrap.dedent(
            f"""Unable to render the template {template!r}: {key!r} unknown.
                - `juju_model`
                - `juju_application`
                - `juju_unit`"""
        )
        super().__init__(msg, *args)


@dataclass
class RouteConfig:
    """Route configuration."""

    root_url: str
    rule: str
    id_: str


@dataclass
class _RouteConfig:
    root_url: str
    rule: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        def _check_var(obj: str, name: str) -> bool:
            error = None
            if not _is_not_empty(obj):
                error = (
                    f"`{name}` not configured; run `juju config <traefik-route-charm> "
                    f"{name}=<{name.upper()}>"
                )

            elif obj != (stripped := obj.strip()):
                error = (
                    f"{name} {obj!r} starts or ends with whitespace;" f"it should be {stripped!r}."
                )

            if error:
                logger.error(error)
            return not error

        if self.root_url:
            try:
                # try rendering with dummy values; it should succeed.
                self.render(model_name="foo", unit_name="bar", app_name="baz")
            except (TemplateKeyError, RuleDerivationError) as e:
                logger.info("Failed to render a template with dummy values")
                logger.error(e)
                return False

        if not self.rule:
            # the rule can be guessed from the root_url
            return _check_var(self.root_url, "root_url")

        valid = starmap(_check_var, ((self.rule, "rule"), (self.root_url, "root_url")))
        return all(valid)

    def render(self, model_name: str, unit_name: str, app_name: str) -> "RouteConfig":
        """Fills in the blanks in the templates."""

        def _render(obj: str) -> Optional[str]:
            # StrictUndefined will raise an exception if some undefined
            # variables are left unrendered in the template
            template = jinja2.Template(obj, undefined=jinja2.StrictUndefined)
            try:
                return template.render(
                    juju_model=model_name, juju_application=app_name, juju_unit=unit_name
                )
            except jinja2.UndefinedError as e:
                undefined_key = e.message.split()[0].strip(r"'")
                raise TemplateKeyError(obj, undefined_key) from e

        url = _render(self.root_url)
        if not self.rule:
            rule = self.generate_rule_from_url(url)
        else:
            rule = _render(self.rule)

        # an easily recognizable id for the traefik services
        id_ = "-".join((unit_name, model_name))
        return RouteConfig(rule=rule, root_url=url, id_=id_)

    @staticmethod
    def generate_rule_from_url(url: str) -> Optional[str]:
        """Derives a Traefik router Host rule from the provided `url`'s hostname."""
        url_ = urlparse(url)
        if not url_.hostname:
            logger.info(f"Parsing url {url_} not valid")
            raise RuleDerivationError(url)
        return f"Host(`{url_.hostname}`)"


def _is_not_empty(config: str) -> bool:
    return bool(config and not config.isspace())


class OathkeeperConfiguratorCharm(CharmBase):
    """Charmed Oathkeeper Configurator."""

    _stored = StoredState()
    _ingress_relation_name = "ingress-per-unit"

    def __init__(self, *args: Any) -> None:
        super().__init__(*args)

        self._stored.set_default(invalid_config=False)

        self.ingress_per_unit = IngressPerUnitProvider(self, self._ingress_relation_name)

        # Charm events
        self.framework.observe(self.on.config_changed, self._on_config_changed)

        # Relation events
        self.framework.observe(
            self.ingress_per_unit.on.data_provided, self._on_ingress_data_provided
        )

    @property
    def access_rules_configured(self) -> bool:
        """Checks whether the access rules have been configured."""
        return _is_not_empty(self.model.config.get("access_rules", ""))

    def validate_access_rules_config(self, config: str) -> None:
        """Validate that the access rules config is a valid json."""
        try:
            json.loads(config)
        except json.JSONDecodeError as e:
            raise InvalidConfigError(f"Failed to decode json: {e}")

    @property
    def _config(self) -> _RouteConfig:
        return _RouteConfig(rule=self.config.get("rule"), root_url=self.config.get("root_url"))

    @property
    def rule(self) -> Optional[str]:
        """The Traefik rule this charm is responsible for configuring."""
        return self._config.rule

    @property
    def root_url(self) -> Optional[str]:
        """The advertised url for the charm requesting ingress."""
        return self._config.root_url

    def _render_config(self, model_name: str, unit_name: str, app_name: str) -> RouteConfig:
        return self._config.render(model_name=model_name, unit_name=unit_name, app_name=app_name)

    @staticmethod
    def _generate_traefik_unit_config(config: RouteConfig) -> UnitConfig:
        rule, config_id, url = config.rule, config.id_, config.root_url

        traefik_router_name = f"juju-{config_id}-router"
        traefik_service_name = f"juju-{config_id}-service"

        config: "UnitConfig" = {
            "router": {
                "rule": rule,
                "service": traefik_service_name,
                "entryPoints": ["web"],
                "middlewares": ["oathkeeper"],
            },
            "router_name": traefik_router_name,
            "service": {"loadBalancer": {"servers": [{"url": url}]}},
            "service_name": traefik_service_name,
        }
        return config

    @staticmethod
    def _merge_traefik_configs(configs: Iterable["UnitConfig"]) -> "TraefikConfig":
        traefik_config = {
            "http": {
                "routers": {config["router_name"]: config["router"] for config in configs},
                "services": {config["service_name"]: config["service"] for config in configs},
            }
        }
        return traefik_config

    def _get_relation(self, endpoint: str) -> Optional[Relation]:
        """Fetches the Relation for endpoint and checks that there's only 1."""
        relations = self.model.relations.get(endpoint)
        if not relations:
            logger.info(f"no relations yet for {endpoint}")
            return None
        if len(relations) > 1:
            logger.warning(f"more than one relation for {endpoint}")
        return relations[0]

    @staticmethod
    def _get_remote_units_from_relation(
        relation: Optional[Relation],
    ) -> Tuple[Unit, ...]:
        if not relation:
            return ()
        return tuple(relation.units)

    @property
    def _ipu_relation(self) -> Optional[Relation]:
        """The relation with the unit requesting ingress."""
        return self._get_relation(self._ingress_relation_name)

    @property
    def _traefik_route_relation(self) -> Optional[Relation]:
        """The relation with the (Traefik) charm providing traefik-route."""
        return self._get_relation(self._traefik_route_relation_name)

    @property
    def _remote_routed_units(self) -> Tuple[Unit, ...]:
        """The remote units in need of ingress."""
        return self._get_remote_units_from_relation(self._ipu_relation)

    def _config_for_unit(self, unit_data: RequirerData) -> RouteConfig:
        """Get the _RouteConfig for the provided `unit_data`."""
        unit_name = unit_data["name"]
        model_name = unit_data["model"]

        # sanity checks
        assert unit_name is not None, "remote unit did not provide its name"
        assert "/" in unit_name, unit_name

        return self._render_config(
            model_name=model_name,
            unit_name=unit_name.replace("/", "-"),
            app_name=unit_name.split("/")[0],
        )

    def _generate_traefik_forwardauth_config(self) -> None:
        ingress: IngressPerUnitProvider = self.ingress_per_unit
        relation = self._ipu_relation

        unit_configs = []
        ready_units = filter(lambda unit_: ingress.is_unit_ready(relation, unit_), relation.units)
        for unit in ready_units:  # units requesting ingress
            unit_data = ingress.get_data(self._ipu_relation, unit)
            config_data = self._config_for_unit(unit_data)
            unit_config = self._generate_traefik_unit_config(config_data)
            unit_configs.append(unit_config)

            logger.info(f"publishing to {unit_data['name']}: {config_data.root_url}")
            ingress.publish_url(relation, unit_data["name"], config_data.root_url)

        config = self._merge_traefik_configs(unit_configs)
        logger.info(f"Generated unit configs: {config}")
        # TODO: Send route configs to traefik via traefik_auth relation

    @property
    def _is_traefik_configuration_valid(self) -> bool:
        if not self._config.is_valid:
            self._stored.invalid_config = True
            return False

        self._stored.invalid_config = False
        return True

    @property
    def _is_traefik_config_ready(self) -> bool:
        if not self._is_traefik_configuration_valid:
            self.unit.status = BlockedStatus("Invalid or missing config. See logs for more info")
            return False

        # validate ingress-per-unit relation status
        if not self._ipu_relation:
            return False
        if not self.ingress_per_unit.is_ready(self._ipu_relation):
            return False

        logger.info("Traefik-related configs and relations are ready")

        return True

    def _on_ingress_data_provided(self, event: IngressDataReadyEvent) -> None:
        if not self._is_traefik_config_ready:
            logger.info("Configurator charm not ready. Deferring the event")
            event.defer()
            return

        self._generate_traefik_forwardauth_config()
        self._on_update_status(event)

    def _on_config_changed(self, event: ConfigChangedEvent) -> None:
        if self.access_rules_configured:
            try:
                self.validate_access_rules_config(self.model.config.get("access_rules"))
                self._stored.invalid_config = False
            except Exception as e:
                self.unit.status = BlockedStatus("Invalid json configuration, see logs")
                logger.error(f"Invalid json configuration: {e.args[0]}")
                self._stored.invalid_config = True
                return

        self.unit.status = MaintenanceStatus("Configuring the charm")

        if self._is_traefik_config_ready:
            self._generate_traefik_forwardauth_config()

        self._on_update_status(event)

    def _on_update_status(self, event: EventBase) -> None:
        """Set the unit status.

        - If the unit is blocked, leave it that way (it means that the config is invalid)
        - If any mandatory config is missing, the status is blocked
        - If the ingress-per-unit relation is missing or not ready, the status is blocked
        - Else status is active
        """
        logger.info(f"Flag value: {self._stored.invalid_config}")
        if self._stored.invalid_config is True:
            return
        if not self.access_rules_configured:
            self.unit.status = BlockedStatus("Missing required configuration value: access_rules")
        # TODO: Non-charms will not require ipu relation, adjust it
        if not self._ipu_relation:
            self.unit.status = BlockedStatus("Awaiting to be related via ingress-per-unit")
            return
        if not self.ingress_per_unit.is_ready(self._ipu_relation):
            self.unit.status = BlockedStatus("ingress-per-unit relation is not ready")
            return
        else:
            self.unit.status = ActiveStatus()


if __name__ == "__main__":
    main(OathkeeperConfiguratorCharm)
