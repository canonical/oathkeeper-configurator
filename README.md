# Charmed Ory Oathkeeper Configurator

## Description

This charm is used to configure and integrate downstream applications with Charmed Ory Oathkeeper and Traefik ForwardAuth middleware.

Please note that this charm is currently work in progress.

## Usage

```bash
juju deploy oathkeeper-configurator
```

You can follow the deployment status with `watch -c juju status --color`.

## Configuration

```bash
juju config oathkeeper-configurator access_rules=@access_rules.json root_url=http://foo.bar/{{juju_model}}-{{juju_unit}}
```

## Integrations

<!-- TODO: Expand once integrations are in place -->

## Security

Security issues can be reported through [LaunchPad](https://wiki.ubuntu.com/DebuggingSecurity#How%20to%20File). Please do not file GitHub issues about security issues.

## Contributing

Please see the [Juju SDK docs](https://juju.is/docs/sdk) for guidelines on enhancements to this
charm following best practice guidelines, and
[CONTRIBUTING.md](https://github.com/canonical/oathkeeper-configurator/blob/main/CONTRIBUTING.md) for developer guidance.

## License

The Charmed Oathkeeper Configurator is free software, distributed under the Apache Software License, version 2.0. See [LICENSE](https://github.com/canonical/oathkeeper-configurator/blob/main/LICENSE) for more information.
