/**
 * DuSu failover front door — Cloudflare Worker.
 *
 * One stable origin (https://dusu.ranabrothers.online) that the app + users hit.
 * Sends traffic to your PC (via a Cloudflare Tunnel) when it's up, and falls back to
 * Render when the PC is off. WebSockets (/ws/interview) pass through both ways.
 *
 * The DATABASE is NOT touched here — both the PC backend and Render use the same Neon
 * Postgres, so failover never splits user data.
 *
 * Configure origins as Worker vars (wrangler.toml [vars] or dashboard):
 *   PC_ORIGIN    = "https://pc.ranabrothers.online"      (cloudflared tunnel → localhost:8000)
 *   CLOUD_ORIGIN = "https://dusu-app-1.onrender.com"     (Render fallback)
 */

const DEFAULTS = {
  PC_ORIGIN: "https://pc.ranabrothers.online",
  CLOUD_ORIGIN: "https://dusu-app-1.onrender.com",
};

// Is the PC origin healthy? Cached ~10s in the edge cache so we don't probe every request.
async function pcHealthy(pcOrigin) {
  const cache = caches.default;
  const key = new Request("https://dusu-health.internal/pc");
  const hit = await cache.match(key);
  if (hit) return (await hit.text()) === "1";

  let ok = false;
  try {
    const r = await fetch(pcOrigin + "/health", { signal: AbortSignal.timeout(1500) });
    ok = r.ok;
  } catch (_) {
    ok = false;
  }
  await cache.put(
    key,
    new Response(ok ? "1" : "0", { headers: { "Cache-Control": "max-age=10" } })
  );
  return ok;
}

export default {
  async fetch(request, env) {
    const PC = (env && env.PC_ORIGIN) || DEFAULTS.PC_ORIGIN;
    const CLOUD = (env && env.CLOUD_ORIGIN) || DEFAULTS.CLOUD_ORIGIN;

    const url = new URL(request.url);
    const isWebSocket = (request.headers.get("Upgrade") || "").toLowerCase() === "websocket";

    const primary = (await pcHealthy(PC)) ? PC : CLOUD;
    const primaryTarget = primary + url.pathname + url.search;

    // Preserve the original request (headers, body, and the WS Upgrade) verbatim.
    try {
      return await fetch(new Request(primaryTarget, request));
    } catch (err) {
      // Mid-flight failure. Can't retry a WebSocket after the upgrade — only plain HTTP.
      if (primary === PC && !isWebSocket) {
        return await fetch(new Request(CLOUD + url.pathname + url.search, request));
      }
      return new Response("DuSu is temporarily unavailable. Please try again.", {
        status: 502,
        headers: { "Content-Type": "text/plain" },
      });
    }
  },
};
