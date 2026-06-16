# Cloudflare Tunnel Route Request — Hermes Console

Copy-paste the block below into Claude-in-Chrome (or any agent with
Cloudflare dashboard access) to provision the public hostname and
Access policy for Hermes Console.

The prompt is self-contained — no follow-up clarification should be
needed. If the agent asks any question, the answer is "use the defaults
that match the existing `southbrook.odooiq.com` / `alfacore.odooiq.com`
routes already configured on tunnel `qnap-odooiq`."

---

## Prompt — paste this verbatim

> Please add a new public hostname to my Cloudflare tunnel and gate it
> behind an email-OTP Access policy. All work happens inside the
> Cloudflare Zero Trust dashboard on my logged-in account.
>
> **Cloudflare account:** dangelo.john@gmail.com
> **Zone:** odooiq.com
> **Tunnel name:** qnap-odooiq
>
> ### Step 1 — Add public hostname
>
> Navigate to Zero Trust → Networks → Tunnels → `qnap-odooiq` → Public
> Hostnames → **Add a public hostname**.
>
> | Field                | Value                  |
> |----------------------|------------------------|
> | Subdomain            | `hermes`               |
> | Domain               | `odooiq.com`            |
> | Path                 | *(leave blank)*        |
> | Type                 | `HTTP`                 |
> | URL                  | `localhost:9080`       |
>
> Under **Additional application settings → TLS**: leave all defaults.
> Under **HTTP Settings**: leave all defaults.
> Under **Connection**: leave all defaults.
>
> Save. Confirm the hostname appears in the tunnel's public-hostnames
> list with status "Healthy" within ~30 seconds.
>
> ### Step 2 — Verify there are no rule conflicts
>
> Before saving, check the existing public hostnames on the tunnel
> (`southbrook.odooiq.com`, `alfacore.odooiq.com`,
> `porterly.odooiq.com`, `tribancs.odooiq.com`, `sapienzium.odooiq.com`,
> `odooiq.com`, `quattroporte.odooiq.com`, `odooai.odooiq.com`,
> `ssh.odooiq.com`). None should be on the literal subdomain `hermes`.
> If any are, STOP and report — do not overwrite.
>
> ### Step 3 — Create Access application
>
> Navigate to Zero Trust → Access → Applications → **Add an
> application** → **Self-hosted**.
>
> | Field                       | Value                                            |
> |-----------------------------|--------------------------------------------------|
> | Application name            | `Hermes Console`                                 |
> | Session duration            | `24 hours`                                       |
> | Application domain          | `hermes.odooiq.com`                               |
> | Path                        | *(leave blank — gate the whole hostname)*        |
> | Identity providers          | Tick the existing **One-time PIN** provider only |
>
> Click **Next** to the policy step.
>
> ### Step 4 — Configure Access policy
>
> Add one policy:
>
> | Field            | Value                                  |
> |------------------|----------------------------------------|
> | Policy name      | `Owner OTP`                            |
> | Action           | `Allow`                                |
> | Session duration | `Same as application`                  |
> | Include rule     | **Selector:** `Emails` &nbsp;&nbsp; **Value:** `dangelo.john@gmail.com` |
>
> No Require rules, no Exclude rules. No other policies.
>
> Click **Next** through any remaining steps (CORS, advanced
> settings) leaving defaults, then **Add application**.
>
> ### Step 5 — Verify end-to-end
>
> Open `https://hermes.odooiq.com` in a fresh incognito window:
> 1. The Cloudflare Access OTP screen should appear (purple
>    "Sign in with One-time PIN" page).
> 2. Enter `dangelo.john@gmail.com`. A code arrives in that inbox.
> 3. Submitting the code should redirect to the Hermes Console UI.
>
> If step 1 returns Cloudflare Error 1033, the tunnel daemon on the
> QNAP is down — report this back and stop; do not edit DNS records
> or change tunnel ingress to mitigate.
>
> If step 1 returns the UI directly with no OTP page, the Access
> application is misconfigured — report back; do not delete the
> route.
>
> ### Step 6 — Report back
>
> Once verified, reply with:
>
> ```
> hermes.odooiq.com  → tunnel qnap-odooiq → http://localhost:9080
> Access policy:  Owner OTP (Allow, emails include dangelo.john@gmail.com)
> Health: healthy
> Last verified: <UTC timestamp>
> ```
>
> No other DNS or zone-level changes are required. Do not touch the
> existing `southbrook.odooiq.com` route or the `ssh.odooiq.com`
> route — they are load-bearing.

---

## After Cloudflare is wired up

Back on the workstation:

```bash
cd /Users/naadmin/hermes-console
./deploy.sh --smoke-only
```

Expect `HTTP 200` from `/api/health`. If you instead get `302` it
means the Access OTP gate is intercepting the unauthenticated `curl` —
that's actually good (proves the gate is live); re-test from a real
browser.
