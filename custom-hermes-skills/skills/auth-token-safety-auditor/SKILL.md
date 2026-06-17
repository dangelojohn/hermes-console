# Auth & Token Safety Auditor

**Skill name:** `auth-token-safety-auditor`
**Category:** `web-services`

## Purpose

Review how a codebase or a config bundle handles authentication and credentials WITHOUT exposing any secret value. Pattern-driven static analysis that flags credential-handling smells (hardcoded keys, plaintext logging, broad scope tokens, missing rotation hooks).

## When to use

- Periodic security audit
- After a credential incident (today's leaked OpenAI key)
- Before publishing any artifact (PR, release, doc, runbook)

## When NOT to use

- As a substitute for human review
- To certify a system free of secrets (best-effort static scan only)

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `target_path` | path | yes | Workspace or single file to scan |
| `strict` | flag | no | Promote some warnings to errors |

## Outputs produced

| Output | Path |
|---|---|
| Audit report | `runs/auth-token-safety-auditor/<target>-<ts>.md` |
| Per-finding pages | `runs/auth-token-safety-auditor/<target>-<ts>-findings/` |

## Step-by-step operating procedure

1. Walk `target_path` for source files (extensions: `py`, `js`, `ts`, `vue`, `yml`, `yaml`, `env`, `conf`, `md`, `json`).
2. **Hardcoded-credential scan**: same regex bank as `skill-integrity-auditor` (OpenAI sk-, Anthropic sk-ant, Google AIza/AQ.Ab8, Groq gsk_, AWS AKIA, GitHub ghp_, Slack xoxb-, RSA/EC private-key headers). NEVER echo the matched substring.
3. **Plaintext-logging scan**: identifiers `api_key`, `password`, `token`, `secret` that appear within 3 lines of `print(`, `log.`, `console.log`, `f"…"` interpolation.
4. **Scope-too-broad scan**: in Cloudflare/GitHub/Forgejo/AWS config: tokens with `*` scope or admin-level role assignments.
5. **Missing-rotation scan**: env vars referenced in code with no rotation runbook in `automation/runbooks/`.
6. **Authorization-bypass scan**: routes / handlers with no auth dependency injection (in FastAPI: missing `Depends(...)`).
7. **Cookie/session smell**: `Set-Cookie` headers without `Secure` / `HttpOnly` / `SameSite`.
8. Emit findings WITHOUT the secret content.

## Web services context

- Hermes Console: Cloudflare Access OTP upstream of Caddy + per-call provider tokens
- Tenant bridges: per-bridge `.env` block with username + password OR X-Api-Key
- Forgejo: per-operation tokens generated + revoked via CLI inside container
- WhatsApp bridge: session persisted in named volume

## Related Need IDs

`N-16`

## Related JTBD IDs

`J-12`

## Safety constraints

- Pure static
- Matched secret content is NEVER echoed (only file:line + match category)
- No exec, no network

## Confirmation requirements

None.

## Validation checklist

- [ ] Every finding has file:line + category but NOT the secret content
- [ ] Hardcoded-credential scan covered all expected file extensions
- [ ] Plaintext-logging false positives are explicitly noted

## Examples

```
$ python3 scripts/run_skill.py auth-token-safety-auditor --target-path ~/hermes-console
→ audit report; today's incident would have been caught at scan time
```

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| False-positive `sk-test-…` | Test placeholder | Use `REDACTED_…` or `placeholder_…` prefixes |

## Source inspiration

See `SOURCE_INSPIRATION.md`.
