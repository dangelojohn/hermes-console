# <Skill Title>

**Skill name:** `<short-kebab-name>` (must match the folder under `skills/`)

**Category:** `<category>` — one of: `odoo-backend`, `odoo-frontend`, `odoo-cloud`, `qnap`, `forgejo`, `web-services`, `python`, `javascript`, `meta`, `documentation`

---

## Purpose

One paragraph: what problem this skill solves, in the operator's words.

## When to use

- Bullet 1
- Bullet 2
- Bullet 3

## When NOT to use

- Bullet 1
- Bullet 2

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `<input>` | string / path / list | yes/no | What shape the caller passes |

## Outputs produced

| Output | Type | Notes |
|---|---|---|
| `<output>` | report / file / pull-request / runbook | Where it lands |

## Step-by-step operating procedure

1. Read-only step
2. Read-only step
3. Read-only step
4. (Optional, gated by confirmation) Action step

Every step that mutates state MUST be gated by an explicit operator confirmation. Steps that only read are unconditionally safe.

## Odoo context (delete if N/A)

- Models / fields / views / controllers touched
- v19 quirks to screen for (link to `ODOO_TECHNICAL_MAP.md` quirk row)

## Odoo Cloud context (delete if N/A)

- Hosting topology + deploy mechanics (see `ODOO_CLOUD_MAP.md`)

## Odoo OWL / JavaScript context (delete if N/A)

- Asset bundles, registries, OWL component lifecycle

## Python context (delete if N/A)

- Modules / packages / virtualenv assumptions

## Forgejo context (delete if N/A)

- Repo, branch, workflow, runner-trust-boundary

## QNAP context (delete if N/A)

- Containers, volumes, ports, daemon socket (`/var/run/system-docker.sock`)

## Web services / API context (delete if N/A)

- Endpoints touched + auth model + idempotency notes

## Related Need IDs

`N-XX`, `N-YY` (from `NEEDS_ASSESSMENT.md`)

## Related JTBD IDs

`J-XX` (from `JTBD_MAP.md`)

## Safety constraints

- Read-only by default
- All write operations require explicit operator confirmation
- No secrets are echoed to logs, stdout, or chat
- All paths are validated against the relevant map (`QNAP_RESOURCE_MAP.md` etc.) before use

## Read-only default behavior

The default invocation MUST be read-only. Any write/destructive mode is opt-in via an explicit `--apply` (or equivalent) flag plus a printed confirmation prompt.

## Confirmation requirements before destructive or production-impacting actions

| Action class | Confirmation required |
|---|---|
| Read | none |
| Local write under `custom-hermes-skills/` | none |
| Local write outside `custom-hermes-skills/` | yes — print diff + ask before applying |
| Container restart, network change, ACL change, ANY production write | yes — print plan + ask + log |

## Validation checklist

- [ ] Dry-run completes without errors
- [ ] Output written to the documented path
- [ ] No secret-pattern strings in output
- [ ] Linked Need ID / JTBD ID resolves
- [ ] Operator can re-run idempotently

## Examples

Provide 1-2 examples of using the skill against the actual workspaces.

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| | | |

## Source inspiration / attribution

See `SOURCE_INSPIRATION.md` in this skill's folder.
