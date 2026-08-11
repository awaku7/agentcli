# Quantities / Unit-Aware Calculations

The `quantities` tool converts units and evaluates physical quantities with [Pint](https://pint.readthedocs.io/).

## Installation

Pint is installed lazily the first time the tool is used. The tool requests `Pint>=0.24.4` through uag's automatic dependency installer; it is not imported or installed during normal startup.

## Examples

```text
25 degC to degF
```

```text
2.5 kW * 8 hour to kWh
```

```text
1 meter + 20 centimeter to meter
```

The optional `to_unit` argument can be used instead of a `to UNIT` suffix. `precision` controls the number of displayed decimal places (0–15, default 6).

## Safety and behavior

- Expressions are parsed as Pint quantity expressions; arbitrary Python execution is not supported.
- Suspicious syntax such as imports, `eval`, `exec`, `lambda`, brackets, braces, and semicolons is rejected before parsing.
- Unknown units and incompatible conversions return a localized error rather than a partial result.
- The tool returns JSON with `ok`, `expression`, `result`, `magnitude`, and `unit` fields.
- The tool is marked `x_parallel_safe` because it creates an independent Pint registry per call.

Supported messages and tool metadata are localized in all supported tool-JSON locales.
