# Migration Notes

This document records what was built in Phase 1, what was deferred, and what's planned for Phase 2-4.

## Per-source-repo decision

Per the policy in `SOURCE_REPOS.md` and `LICENSE_AND_ATTRIBUTION.md`, **no external source repo content was reused** in Phase 1. Every skill was authored from first principles against the user's actual workspaces. The table below records the decision per source repo as catalog-only.

| Source Repo | Source Skill/Pattern | Decision | Reason | Custom Skill Created | Notes |
|---|---|---|---|---|---|
| All 20 listed in `SOURCE_REPOS.md` | (catalog only) | inspiration only — clean-room | Avoids derivative-work risk; allows tighter fit to this workspace | All Phase 1 skills | Each skill's `SOURCE_INSPIRATION.md` records the decision |

## Phase 1: built and validated (20 skills)

| # | Skill | Category | Status |
|---|---|---|---|
| 1 | `odoo-process-analyst` | odoo-backend | ✓ built, validated |
| 2 | `odoo-python-module-engineer` | odoo-backend | ✓ built, validated |
| 3 | `odoo-orm-model-field-mapper` | odoo-backend | ✓ built, validated |
| 4 | `odoo-security-access-auditor` | odoo-backend | ✓ built, validated |
| 5 | `qnap-resource-auditor` | qnap | ✓ built, validated |
| 6 | `qnap-container-ops` | qnap | ✓ built, validated |
| 7 | `qnap-web-services-ops` | qnap | ✓ built, validated |
| 8 | `forgejo-repo-maintainer` | forgejo | ✓ built, validated |
| 9 | `forgejo-actions-ci-engineer` | forgejo | ✓ built, validated |
| 10 | `web-services-api-integrator` | web-services | ✓ built, validated |
| 11 | `skill-integrity-auditor` | meta | ✓ built, validated |
| 12 | `hermes-skill-maintainer` | meta | ✓ built, validated |
| 13 | `documentation-synthesizer` | documentation | ✓ built, validated |
| 14 | `networking-cloudflare-architect` | networking-cloudflare-web-services | ✓ built (mid-turn request) |
| 15 | `network-cloudflare-omada-admin` | networking-cloudflare-web-services | ✓ built (mid-turn request) |
| 16 | `cloudflare-dns-zero-trust-ops` | networking-cloudflare-web-services | ✓ built (mid-turn request) |
| 17 | `tplink-omada-oc200-admin` | networking-cloudflare-web-services | ✓ built (mid-turn request) |
| 18 | `wifi-ssid-vlan-planner` | networking-cloudflare-web-services | ✓ built (mid-turn request) |
| 19 | `network-monitoring-incident-responder` | networking-cloudflare-web-services | ✓ built (mid-turn request) |
| 20 | `network-change-reviewer` | networking-cloudflare-web-services | ✓ built (mid-turn request) |

## Phase 2: scoped, not yet built (12 skills from original 40)

| # | Skill | Category | Reason for deferral |
|---|---|---|---|
| 21 | `odoo-data-import-export-planner` | odoo-backend | High-value but needs a concrete import scenario to test against |
| 22 | `odoo-report-builder` | odoo-backend | Needs a representative report (e.g. PLM ECO report) as the golden |
| 23 | `odoo-troubleshooter` | odoo-backend | Will reuse the v19-quirk list from `odoo-python-module-engineer`; needs runtime log access |
| 24 | `odoo-upgrade-migration-planner` | odoo-backend | Most useful right before a v19→v20 migration; not imminent |
| 25 | `odoo-cloud-ops` | odoo-cloud | The user is self-hosted on QNAP, not Odoo.sh — partial coverage already in `qnap-*` skills |
| 26 | `odoo-owl-component-engineer` | odoo-frontend | Stub via the `owl-js` template; full skill once Phase 2 (customer one-page) lands |
| 27 | `odoo-javascript-web-client-engineer` | odoo-frontend | Same — wait for first non-trivial backend OWL work |
| 28 | `odoo-website-portal-engineer` | odoo-frontend | Stubbed by other skills; full version once portal flows are in scope |
| 29 | `odoo-controller-api-engineer` | odoo-backend | Conceptually covered by `web-services-api-integrator`; standalone version on demand |
| 30 | `webhook-debugger` | web-services | Needs a real webhook delivery log to design against |
| 31 | `service-contract-documenter` | web-services | Partial coverage from `web-services-api-integrator inspect` mode |
| 32 | `auth-token-safety-auditor` | web-services | Pattern partial in `skill-integrity-auditor`; standalone version on demand |

## Phase 3-4: scoped, not yet built (8 skills)

| # | Skill | Category | Reason |
|---|---|---|---|
| 33 | `python-service-engineer` | python | Partially covered by `hermes-skill-maintainer` + `web-services-api-integrator` |
| 34 | `python-odoo-test-runner` | python | Needs a CI environment to validate against |
| 35 | `python-data-cleanup-automation` | python | Needs concrete cleanup scenarios |
| 36 | `javascript-webdev-engineer` | javascript | Partial via templates |
| 37 | `frontend-debugging-analyst` | javascript | Same |
| 38 | `web-app-accessibility-reviewer` | javascript | Specific scope |
| 39 | `qnap-backup-snapshot-checker` | qnap | Backup readiness audit |
| 40 | `qnap-file-governance` | qnap | Shared-folder ACL audit |
| 41 | `qnap-permissions-acl-auditor` | qnap | Could absorb into `qnap-resource-auditor` |
| 42 | `forgejo-release-manager` | forgejo | Once first release lands |
| 43 | `forgejo-issue-triage-analyst` | forgejo | Once issues backlog is real |
| 44 | `repo-needs-assessor` | meta | Partial via `documentation-synthesizer` + `NEEDS_ASSESSMENT.md` |
| 45 | `jtbd-skill-mapper` | meta | Partial via `JTBD_MAP.md` |
| 46 | `skill-factory-custom` | meta | The whole library doubles as a working example |
| 47 | `automation-runbook-builder` | meta | Highest-priority Phase 2 — turns each chat session into a runbook |

## Coverage gaps (Need IDs not yet directly covered)

From `python3 scripts/skill_gap_report.py`:

| Need ID | Coverage status | Next skill to build |
|---|---|---|
| N-06 (UI scaffold) | indirect via templates | `javascript-webdev-engineer` (Phase 3) |
| N-08 (backup readiness) | indirect via `qnap-resource-auditor` | `qnap-backup-snapshot-checker` (Phase 3) |
| N-17 (Python service surface) | partial | `python-service-engineer` (Phase 3) |

All 12 JTBD IDs are covered by at least one Phase 1 skill.

## Tooling / index / validation

| Item | Status |
|---|---|
| `scripts/validate_skills.py` | ✓ built; passes with 0 blockers, 0 warnings |
| `scripts/build_index.py` | ✓ built; regenerates `SKILLS_INDEX.md` deterministically |
| `scripts/license_audit.py` | ✓ built; passes with 0 blockers |
| `scripts/hermes_compat_check.py` | ✓ built; passes with 0 findings |
| `scripts/skill_gap_report.py` | ✓ built; surfaces N-06/N-08/N-17 as gaps |

## Map cross-references added in Phase 1

- `ODOO_PROCESS_MAP.md` ↔ `odoo-process-analyst` + `odoo-orm-model-field-mapper` + `odoo-security-access-auditor`
- `ODOO_TECHNICAL_MAP.md` ↔ `odoo-python-module-engineer` + `odoo-orm-model-field-mapper`
- `ODOO_CLOUD_MAP.md` ↔ `qnap-resource-auditor` + `qnap-container-ops` + `qnap-web-services-ops`
- `QNAP_RESOURCE_MAP.md` ↔ `qnap-*` + `networking-cloudflare-architect` + `network-cloudflare-omada-admin`
- `FORGEJO_REPO_MAP.md` ↔ `forgejo-repo-maintainer` + `forgejo-actions-ci-engineer`
- `WEB_SERVICES_MAP.md` ↔ `web-services-api-integrator` + `networking-cloudflare-architect` + `cloudflare-dns-zero-trust-ops`
