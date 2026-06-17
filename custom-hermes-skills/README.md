# Custom Hermes Skills

A first-principles skills library written for two real workspaces in this user's home directory:

- **`~/hermes-console/`** — the Hermes standalone agent control plane (Python/FastAPI API, Vue 3 PWA UI, WhatsApp bridge sidecar, Caddy+Cloudflare-fronted deploy on a QNAP NAS)
- **`~/southbrook-v19cr/`** — a 30-addon Odoo 19 CE platform (custom configurator, kitchen MRP, manufacturing intelligence, hardware catalog, Hermes bridge addon, Forgejo Actions CI, QNAP deploy)

## Build provenance

Every skill in this library was authored **from first principles** for these workspaces' actual artifacts. None of it is a translation, derivative work, or "minor variation" of any external Hermes/agent-skills repository. The 20 source repos listed in the original brief were not cloned, scraped, or excerpted. They are catalogued in `SOURCE_REPOS.md` by category and license (where publicly known) only, so that future maintainers can investigate independently if they choose.

The format follows the publicly documented `SKILL.md` + `metadata.json` pattern common to multiple agent-skills ecosystems — which is a structural convention, not copyrightable content.

## Phase 1 scope (this delivery)

| Layer | Status |
|---|---|
| Skeleton (skills/, scripts/, templates/, tests/) | ✓ created |
| Seven evidence-based maps (process / technical / cloud / OWL+JS / QNAP / Forgejo / web services) | ✓ filled from real scans |
| Five base templates (base, Odoo backend, Odoo OWL/JS, QNAP, Forgejo) | ✓ created |
| Ten high-priority skills, fully built | ✓ see `SKILLS_INDEX.md` |
| Five validation scripts (validate / index / license / compat / gap) | ✓ executable Python |
| `NEEDS_ASSESSMENT.md`, `JTBD_MAP.md`, `MIGRATION_NOTES.md`, `VALIDATION_REPORT.md` | ✓ |

Skills marked **Phase 2-4** in `MIGRATION_NOTES.md` are scoped but not yet built — they require either user direction on priority or larger time budgets than a single session.

## Safety model

Every skill defaults to **read-only analysis**. Any operation that mutates production state (Odoo data writes, QNAP filesystem changes, git history rewrites, container restarts) requires the skill's user (the model invoking the skill) to gather explicit confirmation from the human operator. This is enforced via:

- Each `SKILL.md`'s **"When NOT to use"** and **"Confirmation requirements"** sections
- A `scripts/skill_integrity_check.py` validator that rejects skills missing safety gates
- Explicit dry-run defaults documented in each operating procedure

Secrets are never echoed. The `scripts/license_audit.py` validator also scans skill files for embedded API key patterns and fails the build if any are detected.

## How to use

```bash
cd custom-hermes-skills

# validate the whole library
python3 scripts/validate_skills.py

# rebuild SKILLS_INDEX.md from current state
python3 scripts/build_index.py

# license + secret-leak audit
python3 scripts/license_audit.py

# Hermes-compatible format compliance
python3 scripts/hermes_compat_check.py

# gap analysis: needs → skills coverage
python3 scripts/skill_gap_report.py
```

## How to add a new skill

1. Copy the closest template from `templates/` into `skills/<your-skill-name>/`
2. Edit `SKILL.md`, `metadata.json`, `SOURCE_INSPIRATION.md`
3. Link to at least one Need ID (`N-…`) from `NEEDS_ASSESSMENT.md` or one JTBD ID (`J-…`) from `JTBD_MAP.md`
4. Run `python3 scripts/validate_skills.py` and `python3 scripts/build_index.py`
5. Commit

## License

This library is original work by the user. Skills can be redistributed under the user's preferred license. See `LICENSE_AND_ATTRIBUTION.md` for the attribution policy applied to any external pattern referenced.
