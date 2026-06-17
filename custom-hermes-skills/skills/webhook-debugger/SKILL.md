# Webhook Debugger

**Skill name:** `webhook-debugger`
**Category:** `web-services`

## Purpose

Trace a webhook producer ↔ consumer pair: payload schemas, signatures, retries, delivery logs, replay safety. Designed against the Hermes Console → southbrook_hermes "Fabio" bridge and inbound webhooks (Forgejo → Odoo, Cloudflare events, WhatsApp).

## When to use

- A webhook isn't delivering OR is double-delivering
- Reviewing a new webhook contract
- Replaying a failed delivery safely

## When NOT to use

- Replaying a delivery whose side-effects are not idempotent
- Modifying the consumer mid-replay

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `producer` | str | yes | E.g. `hermes-console`, `forgejo`, `cloudflare` |
| `consumer` | str | yes | E.g. `southbrook-odoo`, `hermes-api` |
| `delivery_log_path` | path | no | If available |
| `mode` | enum | yes | `inspect` / `audit` / `replay-dry-run` |

## Outputs produced

| Output | Path |
|---|---|
| Trace report | `runs/webhook-debugger/<producer>-to-<consumer>-<ts>.md` |

## Step-by-step operating procedure

### `inspect`

1. Identify producer-side: where the HTTP POST is built. For Hermes Console: `api/tenant_bridges/southbrook_hermes.py::push`. For Forgejo: webhook config on the repo.
2. Identify consumer-side: where the route accepts the POST. For southbrook_hermes: `controllers/main.py::create_recommendation`.
3. Map: HTTP verb, path, content-type, body schema, auth header, idempotency key field.
4. Document each side's retry policy.

### `audit`

1. Check signature verification on the consumer side. Flag if missing.
2. Check idempotency-key handling on the consumer side. Flag if missing.
3. Check producer side for retry-with-backoff + circuit-breaker. Flag if missing.

### `replay-dry-run`

1. Read the failed delivery payload from `delivery_log_path`.
2. Compute the request as it would be sent (NO send).
3. Print the consumer-side log probe command (read-only).
4. Document the rollback if the replay turns out to double-trigger a side effect.

## Web services context

- Hermes Console bridge: per-tenant `_map_to_call_kw_values` + auth via session OR `X-Api-Key` per `.env`
- Forgejo webhooks: HMAC-SHA256 signature in `X-Gitea-Signature` (compatible)
- Cloudflare event delivery: not currently wired in this stack

## Related Need IDs

`N-13`

## Related JTBD IDs

`J-10`

## Safety constraints

- No live replay from this skill
- Idempotency must be confirmed before any operator-driven replay
- Signatures/tokens never echoed

## Confirmation requirements

| Mode | Confirmation |
|---|---|
| `inspect`, `audit`, `replay-dry-run` | none |
| (operator replay) | yes — done outside this skill, with the documented rollback |

## Validation checklist

- [ ] Schemas cited from source
- [ ] Signature + idempotency checks documented
- [ ] Replay dry-run includes a rollback note

## Examples

```
$ python3 scripts/run_skill.py webhook-debugger \
    --producer hermes-console --consumer southbrook-odoo --mode audit
```

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| Consumer 401 | Session expired / api-key mismatch | Re-auth + verify `.env` |
| Producer 524 | Consumer slow > 100s | Move to async + status-poll |

## Source inspiration

See `SOURCE_INSPIRATION.md`.
