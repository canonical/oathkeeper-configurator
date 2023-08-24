# Charmed Ory Oathkeeper Configurator

## Description

This charm is used to configure and integrate downstream applications with Charmed Ory Oathkeeper and Traefik ForwardAuth middleware.

Please note that this charm is currently work in progress.

## Deployment

To deploy this charm, run:
```commandline
juju deploy oathkeeper-configurator
```

You can follow the deployment status with `watch -c juju status --color`.

## Configuration

This charm requires `access_rules` and `root_url` config options to be provided. To set them up, run:
```commandline
juju config oathkeeper-configurator access_rules=@access_rules.json root_url=http://foo.bar/{{juju_model}}-{{juju_unit}}
```
where `access_rules.json` is a json-formatted file that contains the Oathkeeper access rules.

Learn more about access rules [here](https://www.ory.sh/docs/oathkeeper/api-access-rules).

<!-- TODO: Add a note about action to get urls once IAM-427 is done -->

## Integrations

This charm provides an `ingress-per-unit` relation using the `ingress_per_unit` relation interface, with limit 1.
This relation is required to set up ingress routes for charmed workloads.

To integrate a charm using this interface, run:
```commandline
juju integrate oathkeeper-configurator <your-charm>
```

## Security

Security issues can be reported through [LaunchPad](https://wiki.ubuntu.com/DebuggingSecurity#How%20to%20File). Please do not file GitHub issues about security issues.

## Contributing

Please see the [Juju SDK docs](https://juju.is/docs/sdk) for guidelines on enhancements to this
charm following best practice guidelines, and
[CONTRIBUTING.md](https://github.com/canonical/oathkeeper-configurator/blob/main/CONTRIBUTING.md) for developer guidance.

## License

The Charmed Oathkeeper Configurator is free software, distributed under the Apache Software License, version 2.0. See [LICENSE](https://github.com/canonical/oathkeeper-configurator/blob/main/LICENSE) for more information.
