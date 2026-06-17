# Skill Integrity Auditor

**Skill name:** `skill-integrity-auditor`
**Category:** `meta`

## Purpose

Static analysis of this library (and any other agent-skills library it's pointed at) for: missing safety gates, embedded secrets, prompt-injection-bait patterns, destructive operations without confirmation, license attribution gaps.

## When to use

- Before opening a PR that adds or modifies a skill
- Periodic audit of the library
- After importing any external pattern into a skill

## When NOT to use

- As a substitute for human review on security-sensitive skills
- To certify a skill safe for an environment other than the one it was designed for

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `library_path` | path | no | Default `custom-hermes-skills/skills/` |
| `strict` | flag | no | Promote some warnings to errors |

## Outputs produced

| Output | Path |
|---|---|
| Audit report | `runs/skill-integrity-auditor/<ts>.md` |
| Per-skill findings | `runs/skill-integrity-auditor/<ts>-<skill>.md` (when findings present) |

## Step-by-step operating procedure

For each skill under `library_path`:

1. **Structural checks**:
   - `SKILL.md` exists
   - `metadata.json` exists, parses, has `name`, `category`, `summary`, `needs`, `jtbds`, `default_mode`, `destructive_actions`, `requires_confirmation`, `outputs`
   - `SOURCE_INSPIRATION.md` exists
   - At least one Need ID OR one JTBD ID linked (meta-skills are exempted)
2. **Safety checks**:
   - SKILL.md has a "Safety constraints" section with non-empty content
   - If `metadata.json.destructive_actions == true`, SKILL.md has a "Confirmation requirements" section explicitly naming the destructive operations
3. **Secret-pattern scan**: any file in the skill folder containing a string matching one of these regexes is flagged as BLOCKER:
   - `sk-(proj-)?[A-Za-z0-9_-]{20,}` (OpenAI)
   - `sk-ant-api03-[A-Za-z0-9_-]{20,}` (Anthropic)
   - `gsk_[A-Za-z0-9]{20,}` (Groq)
   - `AIza[0-9A-Za-z_-]{20,}` (Google legacy)
   - `AQ\.Ab8[A-Za-z0-9_-]{20,}` (Google new key format)
   - `AKIA[0-9A-Z]{16}` (AWS access key ID)
   - `ghp_[A-Za-z0-9]{20,}` / `ghs_…` / `gho_…` (GitHub tokens)
   - `xoxb-[0-9A-Za-z-]{20,}` (Slack bot token)
   - `-----BEGIN (RSA|EC|OPENSSH|PRIVATE) KEY-----` (private keys)
4. **Prompt-injection-bait scan**: warn on any of:
   - `IGNORE PREVIOUS INSTRUCTIONS`
   - `SYSTEM:`/`USER:`/`ASSISTANT:` text that looks like a chat template inside a SKILL.md (could be exploited if a downstream model reads the skill text)
   - URLs to known prompt-injection demo sites
5. **Destructive-command scan**: warn on any of:
   - `rm -rf` outside an explicit "DO NOT do this" example block
   - `curl <url> | bash`
   - `docker volume prune --force` / `docker system prune --force` / `docker rm -f --volumes`
6. **License / attribution check**: if `SOURCE_INSPIRATION.md` cites an external repo, confirm that file lists a license or marks the license as `unverified` explicitly.
7. **Output dimensions**: confirm `metadata.json.outputs` paths all start with `custom-hermes-skills/runs/` (or the skill's own folder).

Emit one summary report + one per-skill file for any skill with findings.

## Related Need IDs

`N-16`

## Related JTBD IDs

`J-12`

## Safety constraints

- Pure static analysis — no shell exec
- Does not modify any skill file
- Treats every regex match as opaque; never prints the matched substring

## Confirmation requirements

None — read-only.

## Validation checklist

- [ ] Every skill in `library_path` produced a row in the summary
- [ ] BLOCKER findings cite file:line BUT NOT the matched secret content
- [ ] License / attribution check ran against every `SOURCE_INSPIRATION.md`

## Examples

```
$ python3 scripts/skill_integrity_check.py
→ writes runs/skill-integrity-auditor/<ts>.md and per-skill files
```

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| False-positive secret | A test fixture used `sk-test-…` | Use `REDACTED_…` or `placeholder_…` prefix instead |
| Missing-section finding | Section heading typo | Use the exact heading from the template |

## Source inspiration

See `SOURCE_INSPIRATION.md`.
