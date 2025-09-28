// response-summary.ts

export type JsonValue =
  | null
  | string
  | number
  | boolean
  | JsonValue[]
  | { [k: string]: JsonValue };

/** Match "application/json" and variants with parameters. */
export function isJsonContentType(contentType: string | null): boolean {
  if (!contentType) return false;
  const mediaType = contentType.split(";", 1)[0].trim().toLowerCase();
  if (mediaType === "application/json") return true;
  const slash = mediaType.indexOf("/");
  if (slash !== -1) {
    const subtype = mediaType.slice(slash + 1);
    if (subtype.endsWith("+json")) return true;
  }
  return false;
}

function truncate(s: string, max = 200): string {
  if (s.length <= max) return s;
  return s.slice(0, Math.max(0, max - 3)) + "...";
}

export class ResponseSummary {
  readonly ok: boolean;
  readonly status: number;
  readonly has_response_body: boolean;
  readonly text: string;
  readonly data?: JsonValue; // Present only if Content-Type is JSON AND parse succeeded

  constructor(args: {
    ok: boolean;
    status: number;
    has_response_body: boolean;
    text: string;
    data?: JsonValue;
  }) {
    this.ok = args.ok;
    this.status = args.status;
    this.has_response_body = args.has_response_body;
    this.text = args.text;
    this.data = args.data;
  }

  /** Concise string similar to the Python __str__ */
  toString(): string {
    const statusIndicator = this.ok ? "✓" : "✗";
    const parts: string[] = [`${statusIndicator} ${this.status}`];

    if (!this.has_response_body) {
      parts.push("(no body)");
    } else if (this.data !== undefined) {
      const dataStr = truncate(JSON.stringify(this.data));
      parts.push(`JSON: ${dataStr}`);
    } else if (this.text) {
      const textPreview = truncate(this.text.trim());
      parts.push(`Text: ${textPreview}`);
    }

    return parts.join(" | ");
  }
}

/**
 * Summarize a fetch Response.
 * - ok: resp.ok
 * - status: resp.status
 * - has_response_body: true iff any bytes are present
 * - text: always set ("" if no body)
 * - data: only when Content-Type indicates JSON AND body parses
 *
 * Uses resp.clone() so the original Response remains readable by callers.
 */
export default async function summarizeResponse(resp: Response): Promise<ResponseSummary> {
  // Clone once for bytes and once for text to avoid .bodyUsed conflicts
  const bytesClone = resp.clone();
  const textClone = resp.clone();

  // Detect body presence using raw bytes length
  let bodyBytes: ArrayBuffer | null = null;
  try {
    bodyBytes = await bytesClone.arrayBuffer();
  } catch {
    // Some bodies (e.g., network errors) might fail to read; treat as empty
    bodyBytes = null;
  }
  const hasBody = !!bodyBytes && bodyBytes.byteLength > 0;

  // Always provide text; if no body, force ""
  let text = "";
  if (hasBody) {
    try {
      text = await textClone.text();
    } catch {
      text = ""; // decoding failure -> keep empty but preserve hasBody flag
    }
  }

  // Parse JSON only when header explicitly indicates JSON
  const contentType = resp.headers.get("Content-Type");
  let data: JsonValue | undefined = undefined;
  if (hasBody && isJsonContentType(contentType)) {
    try {
      // Parse from text so declared charset/decoding is respected
      data = JSON.parse(text) as JsonValue;
    } catch {
      // Leave data undefined; keep text as-is
    }
  }

  return new ResponseSummary({
    ok: resp.ok,
    status: resp.status,
    has_response_body: hasBody,
    text,
    data,
  });
}

/* ---------- Example usage ----------
async function demo() {
  const r = await fetch("https://httpbin.org/json");
  const s = await summarizeResponse(r);
  console.log(s.toString()); // e.g., "✓ 200 | JSON: {...}"
  // You still can read the original response (we used clone()):
  // const again = await r.text();
}
------------------------------------ */
