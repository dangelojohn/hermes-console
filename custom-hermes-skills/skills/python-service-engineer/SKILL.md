# Python Service Engineer

**Skill name:** `python-service-engineer`
**Category:** `python`

## Purpose

Map a Python service's surface area and surface refactor candidates + test-coverage gaps. Designed against `~/hermes-console/api/` (3,970 lines of Python across 11 files) but applies to any Python service in the workspace.

## When to use

- Periodic health check on a Python service
- Pre-PR audit on a touchy change
- Onboarding a new contributor

## When NOT to use

- Live-running code (this is static analysis only)
- Replacing manual code review for security-sensitive changes

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `service_path` | path | yes | E.g. `~/hermes-console/api` |
| `entrypoint` | str | no | E.g. `main:app` |

## Outputs produced

| Output | Path |
|---|---|
| Surface map | `runs/python-service-engineer/<service>-<ts>.md` |
| Test-coverage estimate | `runs/python-service-engineer/<service>-<ts>-coverage.md` |

## Step-by-step operating procedure

1. Walk `service_path` for `*.py`. Use `ast` to extract every module's:
   - Top-level functions (name, params, return annotation, decorators)
   - Classes (name, bases, methods)
   - Decorators that suggest routes (`@app.get`, `@app.post`, `@http.route`, `@router.*`)
2. Build a route map (for FastAPI / Odoo / Flask services).
3. Identify modules with no `tests/` sibling — flag as untested surface area.
4. Run `pytest --collect-only` (read-only) if `tests/` exists to count test cases.
5. Flag long functions (cyclomatic-complexity proxy: function body > 80 LOC).
6. Flag missing type hints on public functions.
7. Emit reports.

## Python context

- Hermes Console api: FastAPI + Pydantic v2 + httpx + SQLite (WAL) + agent loops
- Standard layout: `api/main.py`, `api/models.py`, `api/llm.py`, `api/local_store.py`, `api/queue.py`, `api/auth.py`, `api/agent_loops.py`, `api/tenant_bridges/`
- Test suite at `api/tests/`

## Related Need IDs

`N-17`

## Related JTBD IDs

`J-09`, `J-10`

## Safety constraints

- AST-only static read
- No import of the service modules (avoids side-effects)
- No `pytest` run (only `--collect-only`)

## Confirmation requirements

None.

## Validation checklist

- [ ] Every `*.py` module has a row
- [ ] Route map cites file:line per route
- [ ] Untested-surface flag matches actual `tests/` layout

## Examples

```
$ python3 scripts/run_skill.py python-service-engineer \
    --service-path ~/hermes-console/api
→ surface map + coverage estimate
```

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| `pytest --collect-only` errors | Imports fail | Skip collection; report fallback estimate |

## Source inspiration

See `SOURCE_INSPIRATION.md`.
