# Python / Odoo Test Runner

**Skill name:** `python-odoo-test-runner`
**Category:** `python`

## Purpose

Identify and run safe Odoo/Python tests: unit tests, integration tests, linting, validation. Maps test inventory + chooses subset to run + reports results without mutating production.

## When to use

- Pre-PR safety pass
- Periodic regression run against a staging DB
- CI-equivalent local sanity check

## When NOT to use

- Running tests against production DB
- Running tests that POST to live external services without mocks

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `target` | path | yes | Hermes API or an Odoo addon |
| `mode` | enum | yes | `inventory` / `run-safe` / `lint` |

## Outputs produced

A report at `runs/python-odoo-test-runner/<target>-<mode>-<ts>.md`.

## Step-by-step operating procedure

### `inventory`

1. For Hermes Console: `pytest --collect-only` against `api/tests/`.
2. For Odoo: walk `addons/<addon>/tests/test_*.py`, count `class Test*` and `def test_*`, tag presence (`@tagged`, `post_install`, `at_install`).

### `run-safe`

1. Identify the safe set: tests that don't depend on a live DB OR can run against a staging DB.
2. Run `pytest -q` against the safe set with timeout.
3. Capture output. Flag failures.

### `lint`

1. Run `ruff` (if available) against the target.
2. Run `black --check`.
3. For Odoo addons: run `pylint --rcfile=$(odoo-pylintrc)` if available, OR `kitchenforge_xml_lint.py` for XML.

## Python / Odoo context

- Hermes Console tests at `~/hermes-console/api/tests/`
- Odoo addon tests follow Odoo convention; `@tagged('post_install', '-at_install')` separates DB-needed vs registry-only tests
- `kitchenforge_xml_lint.py` is the project's XML linter

## Related Need IDs

`N-17`

## Related JTBD IDs

`J-01`, `J-04`

## Safety constraints

- Run only safe tests by default
- Never run against production DB
- Timeout on every test run

## Confirmation requirements

| Mode | Confirmation |
|---|---|
| `inventory`, `lint` | none |
| `run-safe` | none (uses staging or no-DB tests) |
| `run-prod-db` (NOT implemented) | would require explicit confirmation if added |

## Validation checklist

- [ ] Inventory cites every test file
- [ ] `run-safe` results are reproducible
- [ ] Lint findings have file:line

## Examples

```
$ python3 scripts/run_skill.py python-odoo-test-runner \
    --target ~/hermes-console/api --mode inventory
```

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| Tests can't import | `pyproject.toml` not on PYTHONPATH | Run from the project root |

## Source inspiration

See `SOURCE_INSPIRATION.md`.
