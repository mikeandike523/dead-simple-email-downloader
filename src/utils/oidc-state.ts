import crypto from "crypto";

const enc = (buf: Buffer) =>
  buf.toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
const dec = (s: string) => Buffer.from(s.replace(/-/g, "+").replace(/_/g, "/"), "base64");

const SECRET = process.env.OAUTH_STATE_SECRET!;

export function randomString(bytes = 16) {
  return enc(crypto.randomBytes(bytes));
}

export function signState(payload: { n: string; ts: number }) {
  const body = Buffer.from(JSON.stringify(payload));
  const sig = crypto.createHmac("sha256", SECRET).update(body).digest();
  return `${enc(body)}.${enc(sig)}`;
}

export function verifyState(signed: string, maxAgeSec = 600) {
  const [bodyB64, sigB64] = signed.split(".");
  if (!bodyB64 || !sigB64) return null;

  const body = dec(bodyB64);
  const expectedSig = crypto.createHmac("sha256", SECRET).update(body).digest();
  const ok = crypto.timingSafeEqual(expectedSig, dec(sigB64));
  if (!ok) return null;

  const parsed = JSON.parse(body.toString()) as { n: string; ts: number };
  if (!parsed?.n || !parsed?.ts) return null;

  if (Math.floor(Date.now() / 1000) - parsed.ts > maxAgeSec) return null;
  return parsed; // { n, ts }
}

export function decodeJwtPayload<T = any>(jwt: string): T {
  const parts = jwt.split(".");
  if (parts.length < 2) throw new Error("bad jwt");
  const body = parts[1].replace(/-/g, "+").replace(/_/g, "/");
  const pad = "=".repeat((4 - (body.length % 4)) % 4);
  const json = Buffer.from(body + pad, "base64").toString("utf8");
  return JSON.parse(json) as T;
}
