# Validation Report

## Commands run

```
$ python3 scripts/validate_skills.py
Validated 20 skills:
  blockers: 0
  warns:    0

$ python3 scripts/build_index.py
Wrote SKILLS_INDEX.md with 20 skills

$ python3 scripts/license_audit.py
License audit complete. Skills checked: 20. Blockers: 0.

$ python3 scripts/hermes_compat_check.py
Hermes-compat check: 0 findings

$ python3 scripts/skill_gap_report.py
Declared Need IDs: 18 / covered: 15
Declared JTBD IDs: 12 / covered: 12
Uncovered Needs:
  N-06
  N-08
  N-17
```

## Scripts created

| Script | Purpose | Status |
|---|---|---|
| `scripts/validate_skills.py` | Structural + safety + secret-pattern validation per skill | ✓ working |
| `scripts/build_index.py` | Auto-builds `SKILLS_INDEX.md` from `metadata.json` files | ✓ working |
| `scripts/license_audit.py` | License-attribution audit + library-wide secret-pattern scan | ✓ working |
| `scripts/hermes_compat_check.py` | Conformance check against the documented Skills format | ✓ working |
| `scripts/skill_gap_report.py` | Cross-references Need/JTBD docs against skill metadata to find uncovered IDs | ✓ working |

## Validation results

- **Skills built:** 20
- **Validation blockers:** 0
- **Validation warnings:** 0 (after the one mid-build fix to add canonical section headings to the networking-cloudflare-architect SKILL.md)
- **License-audit blockers:** 0
- **Hermes-compat findings:** 0
- **Need coverage:** 15 of 18 (N-06, N-08, N-17 deferred to Phase 2-3 — documented in `MIGRATION_NOTES.md`)
- **JTBD coverage:** 12 of 12 (100%)

## Failures fixed

| Failure | Cause | Resolution |
|---|---|---|
| `networking-cloudflare-architect/SKILL.md`: missing section '## Step-by-step operating procedure' | The skill used per-domain procedure sections (Network discovery / DNS analysis / HTTP-TLS analysis / etc.) instead of one canonical heading | Added a top-level `## Step-by-step operating procedure` section that pointers to the per-domain sections |
| `networking-cloudflare-architect/SKILL.md`: missing section '## Safety constraints' | The skill used `Security & exposure review` + `Confirmation requirements before changes` instead | Added the canonical `## Safety constraints` heading with the consolidated bullet list |

## Known limitations

- **No external source content was retrieved.** The 20 source repos in `SOURCE_REPOS.md` were not cloned in Phase 1. If a future maintainer wants to bring in patterns from any of them, the workflow in `LICENSE_AND_ATTRIBUTION.md` documents the safe path (verify license, re-derive from this workspace's evidence, cite as see-also in `SOURCE_INSPIRATION.md`).
- **No live runtime tests of the skills.** Each `SKILL.md` documents a procedure; the procedures are not yet exercised end-to-end against the QNAP / Cloudflare / Omada. The `validate_skills.py` checks are structural, not runtime.
- **`scripts/run_skill.py` is not built** — the skills assume an invocation harness exists. For Phase 1, the harness is the operator running the documented procedure manually with the current model.
- **20 of the originally-listed 40 skills are deferred to Phase 2-4** per `MIGRATION_NOTES.md`. The deferrals were chosen to maximize Phase 1's coverage of the user's documented incidents and active workspaces; no critical Need ID is uncovered.
- **Need IDs N-06, N-08, N-17** have no direct skill yet; partial coverage exists via related skills. See `MIGRATION_NOTES.md` for the build order.

## Source repos inspected

None cloned. All 20 cataloged by URL pattern only in `SOURCE_REPOS.md`. License verification deferred to a future maintainer who chooses to bring in external content.

## Custom skills created

20 Phase 1 skills across these categories:
- odoo-backend (4): odoo-process-analyst, odoo-python-module-engineer, odoo-orm-model-field-mapper, odoo-security-access-auditor
- qnap (3): qnap-resource-auditor, qnap-container-ops, qnap-web-services-ops
- forgejo (2): forgejo-repo-maintainer, forgejo-actions-ci-engineer
- web-services (1): web-services-api-integrator
- networking-cloudflare-web-services (7): networking-cloudflare-architect, network-cloudflare-omada-admin, cloudflare-dns-zero-trust-ops, tplink-omada-oc200-admin, wifi-ssid-vlan-planner, network-monitoring-incident-responder, network-change-reviewer
- meta (2): skill-integrity-auditor, hermes-skill-maintainer
- documentation (1): documentation-synthesizer

## Gaps requiring manual review

- Whether the `network-change-reviewer` four-class risk taxonomy matches the operator's own thresholds (the operator might want a finer-grained classification)
- Whether the `wifi-ssid-vlan-planner` default-seven segmentation model matches the operator's tolerance for VLAN count (some operators prefer fewer, broader VLANs)
- Whether the `forgejo-repo-maintainer` per-operation-token pattern survives the documented routing flake (in-container API base path should work; external API base path is currently degraded)

## Next recommended improvements

1. Build `automation-runbook-builder` (J-11) — turns each chat session into a `runbooks/<name>.md`. Highest leverage Phase 2 add.
2. Build `qnap-backup-snapshot-checker` (N-08) — closes the largest Need-coverage gap.
3. Build `python-service-engineer` (N-17) — completes the Python surface coverage.
4. Stand up a real `scripts/run_skill.py` harness so the procedure each skill documents can be invoked end-to-end with one command.
5. Run `network-cloudflare-omada-admin` in inventory mode against the live network and check the produced maps against the operator's mental model.
6. Add a tests/ subdirectory per skill with at least one fixture-based unit test for the most critical skills (validate_skills, skill-integrity-auditor, build_index).
