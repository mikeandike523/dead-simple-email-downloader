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

const NO_BODY_STATUS = new Set([204, 304]);

function headerImpliesNoBody(resp: Response): boolean {
  const cl = resp.headers.get("Content-Length");
  if (cl && Number(cl) === 0) return true;
  return false;
}

async function peekHasBody(resp: Response): Promise<boolean> {
  if (NO_BODY_STATUS.has(resp.status)) return false;
  if (headerImpliesNoBody(resp)) return false;
  // If body is null (opaque/cors/head), treat as no body
  if (!resp.body) return false;

  // Clone once to safely read a single chunk
  const peekClone = resp.clone();
  const reader = peekClone.body!.getReader();
  try {
    const { value, done } = await reader.read();
    // If we read something, there *is* a body; if `done` true on first read, it's empty.
    return !!(value && value.byteLength > 0) || !done;
  } catch {
    // If reading fails, be conservative and say "no body"
    return false;
  } finally {
    try { reader.releaseLock(); } catch {}
  }
}

export function stripUtf8Bom(s: string): string {
  return s.charCodeAt(0) === 0xFEFF ? s.slice(1) : s;
}

async function getTextSafely(resp: Response): Promise<string> {
  // Try .text() first (honors declared charset)
  try {
    return await resp.clone().text();
  } catch {
    // Fallback: manual decode from bytes
    try {
      const ab = await resp.clone().arrayBuffer();
      return new TextDecoder().decode(ab);
    } catch {
      return "";
    }
  }
}

type ProblemJson = {
  type?: string;
  title?: string;
  status?: number;
  detail?: string;
  instance?: string;
  error?: { code?: string; message?: string; innerError?: any } | string;
};

function tryProblemCode(d: JsonValue | undefined): string | undefined {
  if (!d || typeof d !== "object") return undefined;
  const pj = d as ProblemJson;
  if (typeof pj.error === "string") return pj.error;
  if (pj.error && typeof pj.error === "object" && "code" in pj.error) {
    const code = (pj.error as any).code;
    return typeof code === "string" ? code : undefined;
  }
  return undefined;
}

export class ResponseSummary<
  T extends JsonValue | undefined | unknown = unknown
> {
  readonly ok: boolean;
  readonly status: number;
  readonly has_response_body: boolean;
  readonly text: string;
  readonly data?: T;
  readonly url?: string;
  readonly contentType?: string | null;
  readonly problemCode?: string;

  constructor(args: {
    ok: boolean;
    status: number;
    has_response_body: boolean;
    text: string;
    data?: T;
    url?: string;
    contentType?: string | null;
    problemCode?: string;
  }) {
    this.ok = args.ok;
    this.status = args.status;
    this.has_response_body = args.has_response_body;
    this.text = args.text;
    this.data = args.data;
    this.url = args.url;
    this.contentType = args.contentType;
    this.problemCode = args.problemCode;
  }

  toString(): string {
    const statusIndicator = this.ok ? "✓" : "✗";
    const parts: string[] = [`${statusIndicator} ${this.status}`];

    if (this.problemCode) parts.push(`[${this.problemCode}]`);

    if (!this.has_response_body) {
      parts.push("(no body)");
    } else if (this.data !== undefined) {
      const dataStr = truncate(JSON.stringify(this.data));
      parts.push(`JSON: ${dataStr}`);
    } else if (this.text) {
      const textPreview = truncate(this.text.trim());
      parts.push(`Text: ${textPreview}`);
    }

    if (this.url) parts.push(`@ ${this.url}`);
    return parts.join(" | ");
  }

  /** Type-narrowing helper for callers */
  hasJson(): this is ResponseSummary<Exclude<T, undefined>> {
    return this.data !== undefined;
  }

  static async from<
    T extends JsonValue | undefined | unknown = unknown
  >(resp: Response) {
    const hasBody = await peekHasBody(resp);

    const contentType = resp.headers.get("Content-Type");
    let text = "";
    let data: JsonValue | undefined = undefined;

    if (hasBody) {
      text = stripUtf8Bom(await getTextSafely(resp));
      if (isJsonContentType(contentType)) {
        try {
          data = JSON.parse(text) as JsonValue;
        } catch {
          // Keep text for diagnostics; leave data undefined
        }
      }
    }

    const summary = new ResponseSummary<T>({
      ok: resp.ok,
      status: resp.status,
      has_response_body: hasBody,
      text,
      data: data as T,
      url: (resp as any).url, // fetch Response usually exposes url
      contentType,
      problemCode: tryProblemCode(data),
    });

    return summary;
  }
}

export default async function summarizeResponse<
  T extends JsonValue | undefined | unknown = unknown
>(resp: Response) {
  return ResponseSummary.from<T>(resp);
}