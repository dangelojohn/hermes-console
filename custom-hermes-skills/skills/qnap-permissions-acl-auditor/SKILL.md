# QNAP Permissions & ACL Auditor

**Skill name:** `qnap-permissions-acl-auditor`
**Category:** `qnap`

## Purpose

Review shared-folder permissions on the QNAP: user/group access, ACL assumptions, risky exposure patterns, least-privilege recommendations. Reads only — never modifies.

## When to use

- Periodic posture review
- After adding a new shared folder or user
- Before a deployment that needs new write paths

## When NOT to use

- Modifying QTS user/group/ACL config (the operator owns that layer per memory `feedback_no_network_or_router_changes.md`)

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `ssh_host` | str | no | Default `admin@ssh.odooiq.com` |
| `share` | str | no | Specific shared folder; default all |

## Outputs produced

| Output | Path |
|---|---|
| ACL report | `runs/qnap-permissions-acl-auditor/<ts>.md` |

## Step-by-step operating procedure

1. Verify SSH = `OdooIQ`.
2. List shares via QTS API or `ls -la /share/`.
3. Per share: read access ACL via `getfacl <path>` (read-only).
4. Per share: list members via QTS user/group introspection (read-only).
5. Flag patterns:
   - World-writable bits
   - Anonymous SMB exposure
   - `guest` user with write on production paths
   - Container-mounted shares where the container UID differs from share owner (UID-100/101 trap per memory)
6. Emit recommendations only — never apply.

## QNAP context

- QTS owns user/group/ACL — DO NOT modify from this skill
- Memory `qnap_demo_stacks.md` documents the UID 100:101 mount-permission fix for the demo stacks
- Backup paths under `/share/CACHEDEV3_DATA/OdooIQ-Backups/` should be locked down

## Related Need IDs

`N-07`, `N-16`

## Related JTBD IDs

`J-05`

## Safety constraints

- Pure read
- Never echo user/group passwords (none are visible via this path anyway)

## Confirmation requirements

None.

## Validation checklist

- [ ] Every share has an entry
- [ ] World-writable findings cite the path
- [ ] Recommendations align with the operator's documented "operator owns network layer" rule

## Examples

```
$ python3 scripts/run_skill.py qnap-permissions-acl-auditor
```

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| getfacl not present | busybox doesn't include it | Fallback to `ls -la` + posix bits only |

## Source inspiration

See `SOURCE_INSPIRATION.md`.
