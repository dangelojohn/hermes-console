# Odoo Security & Access Auditor

**Skill name:** `odoo-security-access-auditor`
**Category:** `odoo-backend`

## Purpose

Cross-addon audit of who can read/write/create/unlink each Odoo model: ACL CSVs, record rules, group hierarchy, menu visibility. Designed to catch the v19 traps (`res.groups.category_id` removal, `groups_id` → `group_ids` rename, missing admin group on a new model, ACL row referring to a model that doesn't exist).

## When to use

- Pre-merge review on a security-sensitive PR
- Periodic ACL audit of `southbrook-odoo`
- After a v19 upgrade, to confirm group membership survived

## When NOT to use

- Modifying any security CSV or XML
- Granting groups via JSON-RPC

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `workspace` | path | yes | E.g. `~/southbrook-v19cr/` |
| `model_filter` | str | no | Regex; default `.*` |

## Outputs produced

| Output | Path | Purpose |
|---|---|---|
| Permission matrix | `runs/odoo-security-access-auditor/<workspace>-<ts>.md` | One row per (model × group), columns rwcu |
| Findings list | `runs/odoo-security-access-auditor/<workspace>-<ts>-findings.md` | Each finding has severity (info/warn/blocker) |

## Step-by-step operating procedure

1. Walk every `addons/*/security/ir.model.access.csv`. Parse each row.
2. Walk every `addons/*/security/*.xml`. Extract `<record model="ir.rule">` and `<record model="res.groups">`.
3. Build the permission matrix: model × group → rwcu.
4. Run findings checks:
   - **WARN** Model defined in `models/` but has no ACL row anywhere
   - **WARN** ACL row references a model with no `_name` declaration in the workspace (might be stock Odoo — OK; might be a typo — not OK)
   - **WARN** `res.groups.category_id` referenced anywhere (removed in v19)
   - **WARN** `res.users.groups_id` referenced in any data file (renamed to `group_ids` in v19)
   - **BLOCKER** Stock admin user (`base.group_user` + `base.group_system`) not granted to a new custom-module security group when that group is the only one referenced by record rules → the addon's UI becomes unreachable for admin
5. Optionally (`--rpc`) verify live: `res.groups.search_read` + check user 2 (admin) membership.
6. Write outputs.

## Odoo context

- ACL CSV columns: `id, name, model_id:id, group_id:id, perm_read, perm_write, perm_create, perm_unlink`
- v19 quirks: see `ODOO_TECHNICAL_MAP.md` rows for `res.groups.category_id` and `groups_id`

## Related Need IDs

`N-03`, `N-16`

## Related JTBD IDs

`J-03`

## Safety constraints

- Pure read of CSV/XML
- `--rpc` mode is read-only `search_read`

## Confirmation requirements

None — read-only.

## Validation checklist

- [ ] Permission matrix has at least one row per model defined in the workspace
- [ ] All BLOCKER findings have a one-line remediation
- [ ] No write outside `runs/`

## Examples

```
$ python3 scripts/run_skill.py odoo-security-access-auditor \
    --workspace ~/southbrook-v19cr
→ matrix + findings — useful for confirming a new addon's admin reachability
```

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| Missing ACL flagged on a stock-Odoo model | Model is upstream Odoo, not in this workspace | Pass `--model-filter '^southbrook\.\|^kitchenforge\.\|^product_graph_'` |

## Source inspiration

See `SOURCE_INSPIRATION.md`.
