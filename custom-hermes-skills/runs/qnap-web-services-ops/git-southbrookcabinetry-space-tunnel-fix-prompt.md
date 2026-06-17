# Chrome Claude prompt — fix git.southbrookcabinetry.space tunnel ingress

Paste this into the Chrome Claude session that has Cloudflare dashboard access.

---

I need you to update one tunnel ingress in Cloudflare.

**Account**: Dangelo.john@gmail.com's Account (ID `2ed2c7f49d4d55d86af59d301e4c39b9`)
**Zero Trust → Networks → Tunnels**: open the tunnel named `qnap-odooiq` (ID `dcc94796-f7b7-45ab-b932-9b746d377c01`).
**Public Hostname tab**: find the row for `git.southbrookcabinetry.space`.

**Current value** (broken):

```
Service:   http
Hostname:  192.168.68.108
Port:      9080
```

**Change to** (matches the working `git.odooiq.com` route):

```
Service:   http
Hostname:  localhost
Port:      9080
```

Then click **Save hostname**. Do NOT touch any of the other 13 public hostnames on this tunnel. Confirm to me when done — I'll verify by re-running a git push.

**Why**: the QNAP's LAN IP changed from `.108` to `.76` (DHCP renewed). The cloudflared connector inside the QNAP can reach itself on `localhost:9080` reliably; pointing at a specific LAN IP made the route fragile, and a stale IP made it fail outright. After this change, HTTPS `git push` to `git.southbrookcabinetry.space/git/<org>/<repo>.git` should succeed instead of returning 307/404.

**Do not** change the apex `southbrookcabinetry.space` route, the `ssh.southbrookcabinetry.space` route, or any other tunnel — only `git.southbrookcabinetry.space`.

---
