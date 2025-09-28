type JsonCheckOptions = {
  /** Accept structured suffix and common variants (application/*+json, application/problem+json, application/ld+json, application/x-json, vendor trees) */
  allowVariants?: boolean;
  /** Accept the non-standard text/json (off by default) */
  allowTextJson?: boolean;
  /** If a charset is present, require it to be UTF-8 (default: true) */
  requireUtf8IfCharset?: boolean;
};

const JSON_TYPES_BASE = ["application/json"];
// A few well-known explicit variants (all covered by +json below, but listed for clarity)
const JSON_TYPES_KNOWN = [
  "application/problem+json",
  "application/ld+json",
  "application/vnd.api+json",
];

export default function isJsonLikeContentType(
  contentType: string | null | undefined,
  {
    allowVariants = false,
    allowTextJson = false,
    requireUtf8IfCharset = true,
  }: JsonCheckOptions = {}
): boolean {
  if (!contentType) return false;

  // Split type/subtype from params; tolerate extra whitespace
  const parts = contentType.split(";").map((s) => s.trim()).filter(Boolean);
  if (parts.length === 0) return false;

  const typePart = parts[0].toLowerCase(); // e.g. "application/json"
  const params = new Map<string, string>();

  // Parse simple key=value params; tolerate quoted values
  for (let i = 1; i < parts.length; i++) {
    const [rawK, rawV] = parts[i].split("=");
    if (!rawK || !rawV) continue;
    const k = rawK.trim().toLowerCase();
    const v = rawV.trim().replace(/^"(.*)"$/, "$1"); // unquote
    params.set(k, v);
  }

  // Enforce charset if present
  if (requireUtf8IfCharset && params.has("charset")) {
    const cs = params.get("charset")!;
    if (cs.toLowerCase() !== "utf-8") return false;
  }

  // Helper: does subtype end with +json (structured syntax suffix)
  const isPlusJson = (): boolean => {
    const slash = typePart.indexOf("/");
    if (slash === -1) return false;
    const subtype = typePart.slice(slash + 1); // after "/"
    return subtype.endsWith("+json");
  };

  // Accept base application/json always
  if (JSON_TYPES_BASE.includes(typePart)) return true;

  if (allowVariants) {
    // Accept application/*+json (RFC 6839), including vendor trees like application/vnd.foo+json
    if (isPlusJson()) return true;

    // Accept a few commonly-seen explicit variants (defensive)
    if (JSON_TYPES_KNOWN.includes(typePart)) return true;

    // Accept legacy/non-standard but still common: application/x-json
    if (typePart === "application/x-json") return true;

    // Optionally accept text/json (very old/non-standard; off by default)
    if (allowTextJson && typePart === "text/json") return true;
  }

  return false;
}