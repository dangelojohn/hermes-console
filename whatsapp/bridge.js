// hermes-whatsapp — bridge between a WhatsApp account (via whatsapp-web.js)
// and hermes-api. Two responsibilities:
//
//   1. Inbound  — every incoming WhatsApp message is POSTed to
//                 ${HERMES_API_URL}/api/whatsapp/inbound. hermes-api decides
//                 how to interpret it (parse "approve N" / "reject N",
//                 thread it as chat, etc.).
//   2. Outbound — hermes-api POSTs to /send on this bridge to deliver a
//                 message to a WhatsApp number it knows about.
//
// Auth is a shared secret in HERMES_WHATSAPP_SHARED_SECRET, required on every
// HTTP call in either direction (X-Hermes-Token header). The bridge talks to
// hermes-api over the hermes-net docker network as `http://hermes-api:8000`.

import { Client, LocalAuth } from "whatsapp-web.js";
import qrcode from "qrcode-terminal";
import express from "express";

const PORT = Number(process.env.WHATSAPP_BRIDGE_PORT || "8901");
const HERMES_API_URL = process.env.HERMES_API_URL || "http://hermes-api:8000";
const SHARED_SECRET = process.env.HERMES_WHATSAPP_SHARED_SECRET || "";
const ALLOWED_SENDERS_RAW = process.env.HERMES_WHATSAPP_ALLOWED_SENDERS || "";
const ALLOWED_SENDERS = new Set(
  ALLOWED_SENDERS_RAW.split(",").map((s) => s.trim()).filter(Boolean),
);
const SESSION_PATH = process.env.WHATSAPP_SESSION_PATH || "/data/whatsapp-session";

if (!SHARED_SECRET) {
  console.warn(
    "[hermes-whatsapp] WARNING: HERMES_WHATSAPP_SHARED_SECRET is unset. " +
      "Bridge will reject every inbound HTTP call. Set it in .env."
  );
}
if (ALLOWED_SENDERS.size === 0) {
  console.warn(
    "[hermes-whatsapp] WARNING: HERMES_WHATSAPP_ALLOWED_SENDERS is empty. " +
      "Bridge will accept zero incoming WhatsApp messages until at least one " +
      "E.164 number is added (comma-separated, e.g. 19055551234,19055559876)."
  );
}

let bridgeReady = false;
let lastQrAt = null;

// ---------------------------------------------------------------------------
// WhatsApp client
// ---------------------------------------------------------------------------

const client = new Client({
  authStrategy: new LocalAuth({ dataPath: SESSION_PATH }),
  puppeteer: {
    args: [
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-dev-shm-usage",
    ],
  },
});

client.on("qr", (qr) => {
  lastQrAt = new Date().toISOString();
  console.log("\n[hermes-whatsapp] Scan this QR with WhatsApp Business → Linked devices:");
  qrcode.generate(qr, { small: true });
  console.log(
    "[hermes-whatsapp] (Same QR available as text at GET /qr — only useful " +
      "to copy into a phone-side QR rendering app.)"
  );
});

client.on("ready", () => {
  bridgeReady = true;
  console.log("[hermes-whatsapp] WhatsApp client ready. Session persisted at", SESSION_PATH);
});

client.on("auth_failure", (msg) => {
  console.error("[hermes-whatsapp] auth_failure:", msg);
  bridgeReady = false;
});

client.on("disconnected", (reason) => {
  console.warn("[hermes-whatsapp] disconnected:", reason);
  bridgeReady = false;
});

// Filter to only the user's allowlisted senders. fromMe (echo of our own
// outbound) is ignored. status broadcasts are ignored.
client.on("message", async (msg) => {
  try {
    if (msg.fromMe) return;
    if (msg.from === "status@broadcast") return;
    // E.164 without "+" or "@c.us"
    const e164 = (msg.from || "").replace(/@c\.us$/, "");
    if (!ALLOWED_SENDERS.has(e164)) {
      console.log(
        `[hermes-whatsapp] dropping message from ${e164} (not in allowlist)`
      );
      return;
    }
    await forwardInbound({
      from: e164,
      body: msg.body || "",
      received_at: new Date(msg.timestamp * 1000).toISOString(),
      message_id: msg.id?._serialized || null,
      has_media: !!msg.hasMedia,
    });
  } catch (err) {
    console.error("[hermes-whatsapp] inbound handler error:", err);
  }
});

async function forwardInbound(payload) {
  const url = `${HERMES_API_URL}/api/whatsapp/inbound`;
  const resp = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Hermes-Token": SHARED_SECRET,
    },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    const text = await resp.text().catch(() => "<no body>");
    console.warn(
      `[hermes-whatsapp] hermes-api returned ${resp.status} for inbound: ${text.slice(0, 200)}`
    );
  }
}

// ---------------------------------------------------------------------------
// HTTP server
// ---------------------------------------------------------------------------

const app = express();
app.use(express.json({ limit: "256kb" }));

function requireSecret(req, res, next) {
  if (!SHARED_SECRET || req.header("X-Hermes-Token") !== SHARED_SECRET) {
    return res.status(401).json({ error: "unauthorized" });
  }
  next();
}

app.get("/health", (_req, res) => {
  res.json({
    ok: true,
    bridge_ready: bridgeReady,
    last_qr_at: lastQrAt,
    allowed_senders_count: ALLOWED_SENDERS.size,
  });
});

// Outbound send — hermes-api POSTs here to deliver a message.
// Body: { to: "19055551234", text: "..."} — `to` is E.164 without +.
app.post("/send", requireSecret, async (req, res) => {
  if (!bridgeReady) {
    return res.status(503).json({ error: "bridge_not_ready" });
  }
  const { to, text } = req.body || {};
  if (!to || typeof to !== "string" || !text || typeof text !== "string") {
    return res.status(400).json({ error: "missing_to_or_text" });
  }
  const chatId = `${to}@c.us`;
  try {
    const sent = await client.sendMessage(chatId, text);
    res.json({ ok: true, message_id: sent.id?._serialized || null });
  } catch (err) {
    console.error("[hermes-whatsapp] send error:", err);
    res.status(500).json({ error: "send_failed", detail: String(err).slice(0, 200) });
  }
});

app.listen(PORT, () => {
  console.log(`[hermes-whatsapp] HTTP server listening on :${PORT}`);
});

// Start the WhatsApp client AFTER the HTTP server is up so /health is
// reachable during the (slow) initial puppeteer boot.
client.initialize().catch((err) => {
  console.error("[hermes-whatsapp] initialize() failed:", err);
});
