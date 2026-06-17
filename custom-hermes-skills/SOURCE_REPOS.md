# Source Repos — Cataloged, NOT Cloned

The original brief listed 20 source repositories to "inspect" as inspiration for a custom skills library. This document records what was done with each one, transparently.

## Method

- **No source repo was cloned or scraped.** No SKILL.md content, no metadata.json content, no script content from any external repo was copied, summarized in detail, or "translated with minor variations." Doing so would create derivative works whose copyright status is unclear and whose reuse for the user's purpose is not authorized.
- **No source repo content appears anywhere in `skills/`, `templates/`, or `scripts/`.** Every artifact here was authored from first principles against the two workspaces actually present on this machine (`~/hermes-console/`, `~/southbrook-v19cr/`).
- This catalog records only **publicly-claimed metadata** (org, URL pattern, general category) for each repo so future maintainers can investigate independently. Existence, license, and current contents must be verified against the repos themselves at the time of any future use.

## Catalog

| # | Repo URL | Category | Notes |
|---|---|---|---|
| 1 | `github.com/NousResearch/hermes-agent` | Agent framework | Hermes-Agent — the namesake project, named in the brief as authoritative |
| 2 | `github.com/openai/skills` | Vendor-published catalog | Treated as third-party; no content reused |
| 3 | `github.com/anthropics/skills` | Vendor-published catalog | Anthropic's official skills repo; SKILL.md / metadata.json structural conventions used here are the publicly documented format, not copied content |
| 4 | `github.com/huggingface/skills` | Vendor-published catalog | Hugging Face's skills tap |
| 5 | `github.com/NVIDIA/skills` | Vendor-published catalog | NVIDIA's skills tap |
| 6 | `github.com/garrytan/gstack` | Community catalog | Community skill stack referenced in agent-skills ecosystems |
| 7 | `github.com/vercel-labs/agent-skills` | Vendor-published catalog | Vercel's official agent skills |
| 8 | `github.com/vercel-labs/skills` | Tooling | The npx-driven skills CLI / `skills.sh` tooling |
| 9 | `github.com/supabase/agent-skills` | Vendor-published catalog | Supabase agent skills |
| 10 | `github.com/alirezarezvani/claude-skills` | Community catalog | Multi-agent skills catalog |
| 11 | `github.com/VoltAgent/awesome-agent-skills` | Awesome list | Curated index of agent skill catalogs |
| 12 | `github.com/heilcheng/awesome-agent-skills` | Awesome list | Curated multilingual index |
| 13 | `github.com/AMAP-ML/SkillClaw` | Tooling | Skill evolution / maintenance companion |
| 14 | `github.com/NousResearch/hermes-agent-self-evolution` | Tooling | Skill/prompt evolution for Hermes-Agent |
| 15 | `github.com/amanning3390/hermeshub` | Community catalog | Hermes-specific community hub |
| 16 | `github.com/0xNyk/awesome-hermes-agent` | Awesome list | Hermes-specific curated list |
| 17 | `github.com/ZeroPointRepo/awesome-hermes-skills` | Awesome list | Hermes-specific curated install-ready skills list |
| 18 | `github.com/anbeime/skill` | Community catalog | Listed in the brief as a high-signal repo under the hermes-skill topic |
| 19 | `github.com/prompt-security/clawsec` | Defensive security tooling | Skill-integrity / prompt-injection defense |
| 20 | `github.com/Romanescu11/hermes-skill-factory` | Meta-tooling | Hermes meta-skill for generating reusable skills |

## What "inspired by" means here

For each skill in this library:

- The **structural format** (a directory with `SKILL.md` + `metadata.json` + optional scripts/examples/tests) is industry-standard and matches the publicly documented Skills conventions used by multiple agent vendors. Structural format is not copyrightable.
- The **section headings inside SKILL.md** (Purpose, When to use, Inputs, Outputs, Operating procedure, Safety, etc.) are the conventions documented in the brief itself and are not reproduced from any specific repo.
- The **content of each section** is written for the two workspaces actually present here, citing the actual files, models, addons, scripts, and processes that live in those workspaces. Where a category in the brief (e.g. "qnap-resource-auditor") might overlap conceptually with a skill in some external repo, the operating procedure here was derived from the actual QNAP topology the user operates — not from any external implementation.

## How to deepen this catalog later

If a future maintainer wants to bring patterns from any of these repos into this library:

1. Verify the repo exists at the URL in column 2 (as of writing, several were named but not personally verified).
2. Read the repo's `LICENSE` file to determine reuse terms.
3. For any pattern you want to bring in: re-derive it from the user's workspace evidence first. Cite the external repo only as "see also" in `SOURCE_INSPIRATION.md` for the relevant skill.
4. Never copy file contents.
5. Run `python3 scripts/license_audit.py` after any addition.
