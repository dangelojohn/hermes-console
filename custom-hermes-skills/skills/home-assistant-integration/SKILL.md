# Home Assistant Integration

**Skill name:** `home-assistant-integration`
**Category:** `web-services`

## Purpose

Operate and audit the Home Assistant tenant bridge that ships with Hermes Console (`api/tenant_bridges/home_assistant.py`). Covers: turning it on, picking a push service vs the default persistent_notification, opting-in to context entities, rotating the long-lived token safely, troubleshooting.

## When to use

- First-time enabling Home Assistant in a Hermes deploy
- Auditing the current HA integration's exposure (which entities can it read, which services can it call)
- Rotating the long-lived access token
- Troubleshooting HA bridge `unreachable` or `401` states

## When NOT to use

- Granting the HA token broader scope than necessary
- Adding context entities without operator allowlist confirmation (the bridge only reads what's explicitly listed)
- Calling HA services from chat without a recommendation flow (use HA automations instead)

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `mode` | enum | yes | `enable` / `audit` / `rotate-token` / `troubleshoot` |
| `ha_url` | URL | no | E.g. `http://homeassistant.local:8123` |
| `push_service` | str | no | E.g. `script.hermes_recommendation_received` |
| `context_entities` | list[str] | no | Allowlist of entity_ids to read |

## Outputs produced

| Output | Path |
|---|---|
| Operation report | `runs/home-assistant-integration/<mode>-<ts>.md` |
| `.env` fragment | `runs/home-assistant-integration/HOME_ASSISTANT.env.fragment` |
| HA automation YAML (if `push_service` requested) | `runs/home-assistant-integration/hermes_automation.yaml` |

## Step-by-step operating procedure

### `enable`

1. Confirm Hermes API can reach the HA URL (DNS + TCP).
2. Generate `.env` fragment with `HOME_ASSISTANT_ENABLED=true` and the other 4 keys.
3. Operator pastes the long-lived token into `.env` (never echoed in chat).
4. Optionally emit a sample HA automation YAML that defines a `script.hermes_recommendation_received` script — operator drops it into HA `scripts.yaml` and reloads scripts.
5. Restart `hermes-api`.
6. Verify via `GET /api/health` — `bridges.home_assistant` should flip to `ok`.

### `audit`

1. Pull current settings from `.env`.
2. Confirm `HOME_ASSISTANT_TOKEN` is set (existence only — never display).
3. List `HOME_ASSISTANT_CONTEXT_ENTITIES`; flag entities outside the documented allowlist.
4. Probe HA `/api/` for health.
5. Probe each context entity (read-only `GET /api/states/<entity>`).

### `rotate-token`

1. Operator creates a NEW long-lived access token in HA (Profile → Long-Lived Access Tokens → CREATE TOKEN). Records the token name.
2. Operator pastes the new token into `.env` (never echoed).
3. Restart `hermes-api`.
4. Verify health is `ok` post-restart.
5. Operator deletes the OLD token in HA. (NOT before health is confirmed.)

### `troubleshoot`

| Symptom | Probable cause | Resolution |
|---|---|---|
| `unreachable` on /api/health | HA URL wrong or HA container down | curl-probe the URL from hermes-api container |
| `401` on push | Token expired or has insufficient scope | rotate-token (above) |
| Push succeeds but no notification | `notification_id` collision OR HA-side automation rejected | check HA Logbook; clear `hermes-<id>` persistent notification |
| 404 on `push_service` | `domain.service` doesn't exist in HA | confirm the script/automation/service exists |

## Web services context

- HA REST API base: `<url>/api/`
- Auth: `Authorization: Bearer <long-lived-token>`
- Default push: `POST /api/services/persistent_notification/create`
- Custom push: `POST /api/services/<domain>/<service>` per `HOME_ASSISTANT_PUSH_SERVICE`
- Context reads: `GET /api/states/<entity_id>` only for allowlisted entities

## Related Need IDs

`N-05`, `N-13`

## Related JTBD IDs

`J-10`

## Safety constraints

- Long-lived token NEVER echoed
- Context entities are an explicit allowlist; the bridge does not iterate states
- Rotation: NEW token verified `ok` BEFORE deleting the OLD token (no lockout)

## Confirmation requirements

| Mode | Confirmation |
|---|---|
| `audit`, `troubleshoot` | none |
| `enable` | operator pastes token + accepts `.env` fragment |
| `rotate-token` | operator follows the documented order |

## Validation checklist

- [ ] Token existence confirmed, value never echoed
- [ ] Context entities limited to allowlist
- [ ] Health is `ok` post-restart

## Examples

```
$ python3 scripts/run_skill.py home-assistant-integration --mode enable \
    --ha-url http://homeassistant.local:8123 \
    --context-entities sensor.office_temperature,binary_sensor.front_door
→ writes .env fragment + sample HA automation YAML
```

## Source inspiration

See `SOURCE_INSPIRATION.md`.
