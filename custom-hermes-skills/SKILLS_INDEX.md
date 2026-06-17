# Skills Index

_Auto-generated from `skills/` by `scripts/build_index.py`. 25 skills._

| Skill | Category | Summary | Needs | JTBDs |
|---|---|---|---|---|
| `odoo-orm-model-field-mapper` | odoo-backend | Per-addon Python AST walk that emits a structured model + field + relation map and v19-quirk flags. | N-01, N-03, N-04 | J-02 |
| `odoo-process-analyst` | odoo-backend | First-line scan of an Odoo workspace producing a process + addon + stakeholder + pain-point map. | N-01, N-02, N-14 | J-02 |
| `odoo-python-module-engineer` | odoo-backend | Per-addon pre-flight: manifest hygiene, data-file alignment, depends correctness, v19 quirk screen, test coverage estimate. | N-02, N-04 | J-01 |
| `odoo-security-access-auditor` | odoo-backend | Cross-addon permission matrix + record-rule audit + v19 security-quirk screen. | N-03, N-16 | J-03 |
| `odoo-troubleshooter` | odoo-backend | Decision-tree triage encoding the user's documented v19 incident history (install fails, asset bundle 500s, cron schema changes, ACL gaps, cold-install gaps). | N-04, N-15 | J-04 |
| `qnap-backup-snapshot-checker` | qnap | Read-only backup-readiness audit: per-site retention conformance, cron status, off-site replication, restore-test recency. | N-08 | J-05 |
| `qnap-container-ops` | qnap | Single-container inspect / logs / exec-readonly / restart / compose-up with destructive-subcommand blacklist + operator confirmation. | N-07, N-15 | J-05, J-09 |
| `qnap-resource-auditor` | qnap | Read-only QNAP container topology audit with optional drift detection against the documented map. | N-07, N-16 | J-05 |
| `qnap-web-services-ops` | qnap | Caddy + Cloudflare-tunnel hostname management: audit, snippet generation, route-prompt generation. | N-09, N-16 | J-06 |
| `forgejo-actions-ci-engineer` | forgejo | Static analysis of Forgejo Actions workflows for trust-boundary risk, unpinned actions, broad permissions, and runner-escape pathways. | N-11, N-16 | J-08 |
| `forgejo-repo-maintainer` | forgejo | Per-operation Forgejo admin: list/create repos, rotate tokens, audit users — all with ephemeral CLI-generated tokens that are revoked at the end of the operation. | N-10, N-16 | J-07 |
| `auth-token-safety-auditor` | web-services | Static analysis of how a codebase handles credentials — without echoing any secret value. Flags hardcoded keys, plaintext logging, broad-scope tokens, missing rotation hooks, auth-bypass routes. | N-16 | J-12 |
| `web-services-api-integrator` | web-services | Inspect an HTTP endpoint to produce its contract, or scaffold a new tenant bridge / LLM provider / webhook following the Hermes Console reference implementations. | N-05, N-12, N-13, N-15 | J-09, J-10 |
| `python-service-engineer` | python | AST-based Python service surface map + route map + untested-module flags + long-function + missing-type-hint findings. | N-17 | J-09, J-10 |
| `cloudflare-dns-zero-trust-ops` | networking-cloudflare-web-services | Cloudflare-only deep ops: DNS, proxy state, SSL/TLS, rulesets, WAF, Access apps, Zero Trust, Tunnel connectors, service tokens, origin certs. | N-09, N-16 | J-06 |
| `network-change-reviewer` | networking-cloudflare-web-services | Pre-change safety review for every Cloudflare / Omada / Wi-Fi / VLAN / DHCP / firewall / DNS / QNAP / Odoo / Forgejo change. Emits a 19-section Change Plan with risk classification and rollback gate. | N-09, N-16 | J-05, J-06 |
| `network-cloudflare-omada-admin` | networking-cloudflare-web-services | End-to-end network admin coordinating Cloudflare + TP-Link Omada (OC200) + Wi-Fi + VLANs + DNS + routing + firewall + monitoring with a strict change-plan-first workflow. | N-07, N-09, N-16 | J-05, J-06 |
| `network-monitoring-incident-responder` | networking-cloudflare-web-services | Structured triage for network / Cloudflare / Omada / QNAP / Odoo / Forgejo incidents: 5-whys, evidence table, safe checks, escalation, rollback, post-incident review. | N-15, N-16 | J-04 |
| `networking-cloudflare-architect` | networking-cloudflare-web-services | Deep networking and Cloudflare operations skill for the user's Odoo/QNAP/Forgejo/Hermes/web-service stack. | N-09, N-12, N-15, N-16 | J-05, J-06, J-09, J-10 |
| `tplink-omada-oc200-admin` | networking-cloudflare-web-services | TP-Link Omada / OC200 controller-side admin: adoption, sites, devices, SSIDs, VLANs, captive portal, firmware, backups, alerts, logs. | N-07, N-09 | J-05, J-06 |
| `wifi-ssid-vlan-planner` | networking-cloudflare-web-services | Pure-planning Wi-Fi / SSID / VLAN / DHCP / firewall design with default-deny inter-VLAN matrix, rollout, and rollback checklists. | N-07, N-09 | J-05 |
| `documentation-synthesizer` | documentation | Extract current-state / open-items / runbook content from sprawling source documents, with mandatory line-level citations. | N-14, N-18 | J-11 |
| `automation-runbook-builder` | meta | Convert a real-execution chat-transcript procedure into a versioned, dry-runnable runbook with rollback and validation. | N-18 | J-11 |
| `hermes-skill-maintainer` | meta | Rebuild the library index, detect duplicates and stale skills, run format-compliance checks, and report Need/JTBD coverage gaps. | N-16 | J-12 |
| `skill-integrity-auditor` | meta | Static analysis of an agent-skills library for safety gates, secrets, prompt-injection bait, destructive commands, and license-attribution gaps. | N-16 | J-12 |

## By category

### odoo-backend (5)

- `odoo-orm-model-field-mapper` — Per-addon Python AST walk that emits a structured model + field + relation map and v19-quirk flags.
- `odoo-process-analyst` — First-line scan of an Odoo workspace producing a process + addon + stakeholder + pain-point map.
- `odoo-python-module-engineer` — Per-addon pre-flight: manifest hygiene, data-file alignment, depends correctness, v19 quirk screen, test coverage estimate.
- `odoo-security-access-auditor` — Cross-addon permission matrix + record-rule audit + v19 security-quirk screen.
- `odoo-troubleshooter` — Decision-tree triage encoding the user's documented v19 incident history (install fails, asset bundle 500s, cron schema changes, ACL gaps, cold-install gaps).

### qnap (4)

- `qnap-backup-snapshot-checker` — Read-only backup-readiness audit: per-site retention conformance, cron status, off-site replication, restore-test recency.
- `qnap-container-ops` — Single-container inspect / logs / exec-readonly / restart / compose-up with destructive-subcommand blacklist + operator confirmation.
- `qnap-resource-auditor` — Read-only QNAP container topology audit with optional drift detection against the documented map.
- `qnap-web-services-ops` — Caddy + Cloudflare-tunnel hostname management: audit, snippet generation, route-prompt generation.

### forgejo (2)

- `forgejo-actions-ci-engineer` — Static analysis of Forgejo Actions workflows for trust-boundary risk, unpinned actions, broad permissions, and runner-escape pathways.
- `forgejo-repo-maintainer` — Per-operation Forgejo admin: list/create repos, rotate tokens, audit users — all with ephemeral CLI-generated tokens that are revoked at the end of the operation.

### web-services (2)

- `auth-token-safety-auditor` — Static analysis of how a codebase handles credentials — without echoing any secret value. Flags hardcoded keys, plaintext logging, broad-scope tokens, missing rotation hooks, auth-bypass routes.
- `web-services-api-integrator` — Inspect an HTTP endpoint to produce its contract, or scaffold a new tenant bridge / LLM provider / webhook following the Hermes Console reference implementations.

### python (1)

- `python-service-engineer` — AST-based Python service surface map + route map + untested-module flags + long-function + missing-type-hint findings.

### networking-cloudflare-web-services (7)

- `cloudflare-dns-zero-trust-ops` — Cloudflare-only deep ops: DNS, proxy state, SSL/TLS, rulesets, WAF, Access apps, Zero Trust, Tunnel connectors, service tokens, origin certs.
- `network-change-reviewer` — Pre-change safety review for every Cloudflare / Omada / Wi-Fi / VLAN / DHCP / firewall / DNS / QNAP / Odoo / Forgejo change. Emits a 19-section Change Plan with risk classification and rollback gate.
- `network-cloudflare-omada-admin` — End-to-end network admin coordinating Cloudflare + TP-Link Omada (OC200) + Wi-Fi + VLANs + DNS + routing + firewall + monitoring with a strict change-plan-first workflow.
- `network-monitoring-incident-responder` — Structured triage for network / Cloudflare / Omada / QNAP / Odoo / Forgejo incidents: 5-whys, evidence table, safe checks, escalation, rollback, post-incident review.
- `networking-cloudflare-architect` — Deep networking and Cloudflare operations skill for the user's Odoo/QNAP/Forgejo/Hermes/web-service stack.
- `tplink-omada-oc200-admin` — TP-Link Omada / OC200 controller-side admin: adoption, sites, devices, SSIDs, VLANs, captive portal, firmware, backups, alerts, logs.
- `wifi-ssid-vlan-planner` — Pure-planning Wi-Fi / SSID / VLAN / DHCP / firewall design with default-deny inter-VLAN matrix, rollout, and rollback checklists.

### documentation (1)

- `documentation-synthesizer` — Extract current-state / open-items / runbook content from sprawling source documents, with mandatory line-level citations.

### meta (3)

- `automation-runbook-builder` — Convert a real-execution chat-transcript procedure into a versioned, dry-runnable runbook with rollback and validation.
- `hermes-skill-maintainer` — Rebuild the library index, detect duplicates and stale skills, run format-compliance checks, and report Need/JTBD coverage gaps.
- `skill-integrity-auditor` — Static analysis of an agent-skills library for safety gates, secrets, prompt-injection bait, destructive commands, and license-attribution gaps.

