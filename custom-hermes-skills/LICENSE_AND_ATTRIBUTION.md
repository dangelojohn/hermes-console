# License & Attribution Policy

## License of this library

All files under `custom-hermes-skills/` are **original work** authored against the user's workspaces. Default license: same as the user's preferred license for their own work (the user is the sole copyright holder).

## Attribution policy

This library does not reproduce any external Hermes/agent-skills repository content. Where a generic concept could be said to "overlap" with publicly-known agent-skills conventions (the structural format of `SKILL.md` + `metadata.json`, the section headings in the brief), that overlap reflects either (a) format documented publicly by multiple agent vendors as the canonical Skills convention, which is not copyrightable, or (b) section names given in the original brief itself.

No source repo was cloned, scraped, or excerpted in the process of authoring this library. The 20 repos named in the brief are cataloged in `SOURCE_REPOS.md` only by URL pattern and category — license verification was deliberately deferred to a future maintainer who chooses to investigate any specific repo for reuse.

## If a future maintainer adds content from an external source

1. **Verify the source repo's license** before adding anything. Note both the SPDX identifier and the version of the license file at the time of import.
2. **Prefer first-principles re-derivation** over copy-with-modification. The result is yours to license; a derivative is not.
3. **If you do bring external text or code** in: cite it in the relevant skill's `SOURCE_INSPIRATION.md` with the source repo, the commit SHA, and the upstream license. Run `python3 scripts/license_audit.py` to confirm the attribution is present and the secret-pattern scan is clean.
4. **Never import secrets** (API keys, tokens, passwords) even from your own private repos. The `license_audit.py` script rejects any file containing common key patterns (`sk-`, `gsk_`, `xoxb-`, `AIza`, `AKIA`, `ghp_`, etc.).

## Concept-overlap notes

Some sections of the original brief named skill categories that are conceptually common across the agent-skills space (e.g. "skill-integrity-auditor", "documentation-synthesizer"). These names are not copyrightable. The implementation under `skills/<skill-name>/SKILL.md` for each was written from this workspace's evidence — not adapted from any specific external repo.
