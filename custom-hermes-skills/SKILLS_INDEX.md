# Skills Index

_Auto-generated from `skills/` by `scripts/build_index.py`. 43 skills._

| Skill | Category | Summary | Needs | JTBDs |
|---|---|---|---|---|
| `odoo-controller-api-engineer` | odoo-backend | Audit + scaffold for Odoo HTTP controllers: @http.route, auth, CORS, CSRF, idempotency, error envelopes, ACL rows. | N-05, N-13 | J-09, J-10 |
| `odoo-orm-model-field-mapper` | odoo-backend | Per-addon Python AST walk that emits a structured model + field + relation map and v19-quirk flags. | N-01, N-03, N-04 | J-02 |
| `odoo-process-analyst` | odoo-backend | First-line scan of an Odoo workspace producing a process + addon + stakeholder + pain-point map. | N-01, N-02, N-14 | J-02 |
| `odoo-python-module-engineer` | odoo-backend | Per-addon pre-flight: manifest hygiene, data-file alignment, depends correctness, v19 quirk screen, test coverage estimate. | N-02, N-04 | J-01 |
| `odoo-security-access-auditor` | odoo-backend | Cross-addon permission matrix + record-rule audit + v19 security-quirk screen. | N-03, N-16 | J-03 |
| `odoo-troubleshooter` | odoo-backend | Decision-tree triage encoding the user's documented v19 incident history (install fails, asset bundle 500s, cron schema changes, ACL gaps, cold-install gaps). | N-04, N-15 | J-04 |
| `odoo-upgrade-migration-planner` | odoo-backend | Major-version upgrade and data migration planner: per-module quirk screen, migrate(cr,version) skeletons, rollback, staging-DB validation. | N-04 | J-01 |
| `odoo-javascript-web-client-engineer` | odoo-frontend | Asset-bundle, registry, patch, and debugging skill for the Odoo JS web client; sister to odoo-owl-component-engineer. | N-04, N-06 | J-04 |
| `odoo-owl-component-engineer` | odoo-frontend | Map + scaffold OWL components, services, registries, templates inside Odoo addons. | N-06 | J-09 |
| `odoo-website-portal-engineer` | odoo-frontend | Build and audit Odoo website + portal flows (QWeb templates, /my/* routes, forms, CSRF, XSS guards). | N-06, N-16 | J-09 |
| `qnap-backup-snapshot-checker` | qnap | Read-only backup-readiness audit: per-site retention conformance, cron status, off-site replication, restore-test recency. | N-08 | J-05 |
| `qnap-container-ops` | qnap | Single-container inspect / logs / exec-readonly / restart / compose-up with destructive-subcommand blacklist + operator confirmation. | N-07, N-15 | J-05, J-09 |
| `qnap-permissions-acl-auditor` | qnap | Read-only ACL audit on QNAP shared folders: posix bits, getfacl, user/group membership, container UID alignment. | N-07, N-16 | J-05 |
| `qnap-resource-auditor` | qnap | Read-only QNAP container topology audit with optional drift detection against the documented map. | N-07, N-16 | J-05 |
| `qnap-web-services-ops` | qnap | Caddy + Cloudflare-tunnel hostname management: audit, snippet generation, route-prompt generation. | N-09, N-16 | J-06 |
| `forgejo-actions-ci-engineer` | forgejo | Static analysis of Forgejo Actions workflows for trust-boundary risk, unpinned actions, broad permissions, and runner-escape pathways. | N-11, N-16 | J-08 |
| `forgejo-issue-triage-analyst` | forgejo | Convert Forgejo issues into Need IDs, JTBDs, acceptance criteria, and skill recommendations. | N-10, N-14 | J-07 |
| `forgejo-release-manager` | forgejo | Generate release notes, CHANGELOG fragments, and documented tag + release-API commands for Forgejo repos. | N-10 | J-07 |
| `forgejo-repo-maintainer` | forgejo | Per-operation Forgejo admin: list/create repos, rotate tokens, audit users — all with ephemeral CLI-generated tokens that are revoked at the end of the operation. | N-10, N-16 | J-07 |
| `auth-token-safety-auditor` | web-services | Static analysis of how a codebase handles credentials — without echoing any secret value. Flags hardcoded keys, plaintext logging, broad-scope tokens, missing rotation hooks, auth-bypass routes. | N-16 | J-12 |
| `home-assistant-integration` | web-services | Operate and audit the Home Assistant tenant bridge: enable, audit, rotate the long-lived token safely, troubleshoot. | N-05, N-13 | J-10 |
| `service-contract-documenter` | web-services | Generate API / service contract documentation in markdown / OpenAPI / runbook format with placeholder-only examples. | N-05, N-13 | J-10 |
| `web-services-api-integrator` | web-services | Inspect an HTTP endpoint to produce its contract, or scaffold a new tenant bridge / LLM provider / webhook following the Hermes Console reference implementations. | N-05, N-12, N-13, N-15 | J-09, J-10 |
| `webhook-debugger` | web-services | Trace + audit + replay-dry-run for a producer↔consumer webhook pair (Hermes→Odoo, Forgejo→Odoo, etc.). No live replay. | N-13 | J-10 |
| `python-odoo-test-runner` | python | Inventory + safe-run + lint for Python/Odoo tests with no production-DB risk. | N-17 | J-01, J-04 |
| `python-service-engineer` | python | AST-based Python service surface map + route map + untested-module flags + long-function + missing-type-hint findings. | N-17 | J-09, J-10 |
| `javascript-webdev-engineer` | javascript | Map + scaffold Vue 3 PWA features (view, store slice, nav entry) following the Hermes Console UI conventions. | N-06, N-17 | J-09 |
| `cloudflare-dns-zero-trust-ops` | networking-cloudflare-web-services | Cloudflare-only deep ops: DNS, proxy state, SSL/TLS, rulesets, WAF, Access apps, Zero Trust, Tunnel connectors, service tokens, origin certs. | N-09, N-16 | J-06 |
| `network-change-reviewer` | networking-cloudflare-web-services | Pre-change safety review for every Cloudflare / Omada / Wi-Fi / VLAN / DHCP / firewall / DNS / QNAP / Odoo / Forgejo change. Emits a 19-section Change Plan with risk classification and rollback gate. | N-09, N-16 | J-05, J-06 |
| `network-cloudflare-omada-admin` | networking-cloudflare-web-services | End-to-end network admin coordinating Cloudflare + TP-Link Omada (OC200) + Wi-Fi + VLANs + DNS + routing + firewall + monitoring with a strict change-plan-first workflow. | N-07, N-09, N-16 | J-05, J-06 |
| `network-monitoring-incident-responder` | networking-cloudflare-web-services | Structured triage for network / Cloudflare / Omada / QNAP / Odoo / Forgejo incidents: 5-whys, evidence table, safe checks, escalation, rollback, post-incident review. | N-15, N-16 | J-04 |
| `networking-cloudflare-architect` | networking-cloudflare-web-services | Deep networking and Cloudflare operations skill for the user's Odoo/QNAP/Forgejo/Hermes/web-service stack. | N-09, N-12, N-15, N-16 | J-05, J-06, J-09, J-10 |
| `tplink-omada-oc200-admin` | networking-cloudflare-web-services | TP-Link Omada / OC200 controller-side admin: adoption, sites, devices, SSIDs, VLANs, captive portal, firmware, backups, alerts, logs. | N-07, N-09 | J-05, J-06 |
| `wifi-ssid-vlan-planner` | networking-cloudflare-web-services | Pure-planning Wi-Fi / SSID / VLAN / DHCP / firewall design with default-deny inter-VLAN matrix, rollout, and rollback checklists. | N-07, N-09 | J-05 |
| `documentation-synthesizer` | documentation | Extract current-state / open-items / runbook content from sprawling source documents, with mandatory line-level citations. | N-14, N-18 | J-11 |
| `automation-runbook-builder` | meta | Convert a real-execution chat-transcript procedure into a versioned, dry-runnable runbook with rollback and validation. | N-18 | J-11 |
| `hermes-mcp-service` | meta | Operator-facing reference for the Hermes MCP service: setup, troubleshooting, audit, key rotation. | N-16, N-18 | J-09, J-10, J-12 |
| `hermes-skill-maintainer` | meta | Rebuild the library index, detect duplicates and stale skills, run format-compliance checks, and report Need/JTBD coverage gaps. | N-16 | J-12 |
| `jtbd-skill-mapper` | meta | Cross-reference JTBDs against built skills; produce coverage matrix or ranked recommendation for the next skill to build. | N-18 | J-11, J-12 |
| `repo-needs-assessor` | meta | Top-level scan that produces or updates a workspace's NEEDS_ASSESSMENT, JTBD_MAP, and per-domain maps. | N-14, N-18 | J-11 |
| `self-learning-loop` | meta | Continuous-improvement mechanism: collect per-skill run outcomes, roll up patterns, propose incremental SKILL.md edits. The 'self-learning on' switch for the whole library. | N-18 | J-11, J-12 |
| `skill-factory-custom` | meta | Generate new Hermes-compatible skills from a documented procedure + a category + Need/JTBD anchors. | N-18 | J-11, J-12 |
| `skill-integrity-auditor` | meta | Static analysis of an agent-skills library for safety gates, secrets, prompt-injection bait, destructive commands, and license-attribution gaps. | N-16 | J-12 |

## By category

### odoo-backend (7)

- `odoo-controller-api-engineer` — Audit + scaffold for Odoo HTTP controllers: @http.route, auth, CORS, CSRF, idempotency, error envelopes, ACL rows.
- `odoo-orm-model-field-mapper` — Per-addon Python AST walk that emits a structured model + field + relation map and v19-quirk flags.
- `odoo-process-analyst` — First-line scan of an Odoo workspace producing a process + addon + stakeholder + pain-point map.
- `odoo-python-module-engineer` — Per-addon pre-flight: manifest hygiene, data-file alignment, depends correctness, v19 quirk screen, test coverage estimate.
- `odoo-security-access-auditor` — Cross-addon permission matrix + record-rule audit + v19 security-quirk screen.
- `odoo-troubleshooter` — Decision-tree triage encoding the user's documented v19 incident history (install fails, asset bundle 500s, cron schema changes, ACL gaps, cold-install gaps).
- `odoo-upgrade-migration-planner` — Major-version upgrade and data migration planner: per-module quirk screen, migrate(cr,version) skeletons, rollback, staging-DB validation.

### odoo-frontend (3)

- `odoo-javascript-web-client-engineer` — Asset-bundle, registry, patch, and debugging skill for the Odoo JS web client; sister to odoo-owl-component-engineer.
- `odoo-owl-component-engineer` — Map + scaffold OWL components, services, registries, templates inside Odoo addons.
- `odoo-website-portal-engineer` — Build and audit Odoo website + portal flows (QWeb templates, /my/* routes, forms, CSRF, XSS guards).

### qnap (5)

- `qnap-backup-snapshot-checker` — Read-only backup-readiness audit: per-site retention conformance, cron status, off-site replication, restore-test recency.
- `qnap-container-ops` — Single-container inspect / logs / exec-readonly / restart / compose-up with destructive-subcommand blacklist + operator confirmation.
- `qnap-permissions-acl-auditor` — Read-only ACL audit on QNAP shared folders: posix bits, getfacl, user/group membership, container UID alignment.
- `qnap-resource-auditor` — Read-only QNAP container topology audit with optional drift detection against the documented map.
- `qnap-web-services-ops` — Caddy + Cloudflare-tunnel hostname management: audit, snippet generation, route-prompt generation.

### forgejo (4)

- `forgejo-actions-ci-engineer` — Static analysis of Forgejo Actions workflows for trust-boundary risk, unpinned actions, broad permissions, and runner-escape pathways.
- `forgejo-issue-triage-analyst` — Convert Forgejo issues into Need IDs, JTBDs, acceptance criteria, and skill recommendations.
- `forgejo-release-manager` — Generate release notes, CHANGELOG fragments, and documented tag + release-API commands for Forgejo repos.
- `forgejo-repo-maintainer` — Per-operation Forgejo admin: list/create repos, rotate tokens, audit users — all with ephemeral CLI-generated tokens that are revoked at the end of the operation.

### web-services (5)

- `auth-token-safety-auditor` — Static analysis of how a codebase handles credentials — without echoing any secret value. Flags hardcoded keys, plaintext logging, broad-scope tokens, missing rotation hooks, auth-bypass routes.
- `home-assistant-integration` — Operate and audit the Home Assistant tenant bridge: enable, audit, rotate the long-lived token safely, troubleshoot.
- `service-contract-documenter` — Generate API / service contract documentation in markdown / OpenAPI / runbook format with placeholder-only examples.
- `web-services-api-integrator` — Inspect an HTTP endpoint to produce its contract, or scaffold a new tenant bridge / LLM provider / webhook following the Hermes Console reference implementations.
- `webhook-debugger` — Trace + audit + replay-dry-run for a producer↔consumer webhook pair (Hermes→Odoo, Forgejo→Odoo, etc.). No live replay.

### python (2)

- `python-odoo-test-runner` — Inventory + safe-run + lint for Python/Odoo tests with no production-DB risk.
- `python-service-engineer` — AST-based Python service surface map + route map + untested-module flags + long-function + missing-type-hint findings.

### javascript (1)

- `javascript-webdev-engineer` — Map + scaffold Vue 3 PWA features (view, store slice, nav entry) following the Hermes Console UI conventions.

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

### meta (8)

- `automation-runbook-builder` — Convert a real-execution chat-transcript procedure into a versioned, dry-runnable runbook with rollback and validation.
- `hermes-mcp-service` — Operator-facing reference for the Hermes MCP service: setup, troubleshooting, audit, key rotation.
- `hermes-skill-maintainer` — Rebuild the library index, detect duplicates and stale skills, run format-compliance checks, and report Need/JTBD coverage gaps.
- `jtbd-skill-mapper` — Cross-reference JTBDs against built skills; produce coverage matrix or ranked recommendation for the next skill to build.
- `repo-needs-assessor` — Top-level scan that produces or updates a workspace's NEEDS_ASSESSMENT, JTBD_MAP, and per-domain maps.
- `self-learning-loop` — Continuous-improvement mechanism: collect per-skill run outcomes, roll up patterns, propose incremental SKILL.md edits. The 'self-learning on' switch for the whole library.
- `skill-factory-custom` — Generate new Hermes-compatible skills from a documented procedure + a category + Need/JTBD anchors.
- `skill-integrity-auditor` — Static analysis of an agent-skills library for safety gates, secrets, prompt-injection bait, destructive commands, and license-attribution gaps.

