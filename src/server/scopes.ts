export type Provider = "exchange" | "google";
export type Product = "outlook" | "teams" | "gmail" | "drive";

type CommandScopeMap = Record<string, string[]>;

type ProductEntry = {
  base: string[];
  commands: CommandScopeMap;
};

type ScopeRegistry = Record<Provider, Partial<Record<Product, ProductEntry>>>;

export const SCOPE_REGISTRY: ScopeRegistry = {
  exchange: {
    outlook: {
      base: [
        "openid",
        "offline_access",
        "User.Read",
        "Mail.Read",
      ],
      commands: {
        // read-only commands need nothing beyond base
        "me":            [],
        "folders":       [],
        "index":         [],
        "total-emails":  [],
        // write-capable commands
        "download":      ["Mail.Read.Shared"],
        "output":        [],
        "safe-delete":   ["Mail.ReadWrite", "Mail.ReadWrite.Shared"],
        "debug-download": [],
      },
    },
    teams: {
      base: [
        "openid",
        "offline_access",
        "User.Read",
        "Chat.Read",
      ],
      commands: {},
    },
  },
  google: {
    gmail: {
      base: [
        "openid",
        "email",
        "profile",
        "https://www.googleapis.com/auth/gmail.readonly",
      ],
      commands: {
        "me":       [],
        "folders":  [],
        "list":     [],
        "download": [],
        // TUI for categorizing / deleting junk — needs modify
        "manage":   ["https://www.googleapis.com/auth/gmail.modify"],
      },
    },
    drive: {
      base: [
        "openid",
        "email",
        "profile",
        "https://www.googleapis.com/auth/drive.readonly",
      ],
      commands: {},
    },
  },
};

/**
 * Returns the deduplicated union of base scopes + any extra scopes
 * required by the specified commands.  Unknown commands are silently ignored.
 */
export function resolveScopes(
  provider: Provider,
  product: Product,
  commands?: string[]
): string[] {
  const entry = SCOPE_REGISTRY[provider]?.[product];
  if (!entry) return [];
  const extra = (commands ?? []).flatMap((cmd) => entry.commands[cmd] ?? []);
  return [...new Set([...entry.base, ...extra])];
}

/**
 * Returns a breakdown useful for the /scopes inspection endpoint.
 *
 * - `allCommandScopes`: every known command and its extra scopes (always included for reference)
 * - `selectedCommandScopes`: only the commands explicitly requested (empty when none specified)
 * - `resolved`: the union that would actually be sent to the OAuth provider
 */
export function describeScopeRequest(
  provider: Provider,
  product: Product,
  commands?: string[]
): {
  base: string[];
  allCommandScopes: Record<string, string[]>;
  selectedCommandScopes: Record<string, string[]>;
  resolved: string[];
  unknownCommands: string[];
} {
  const entry = SCOPE_REGISTRY[provider]?.[product];
  if (!entry) {
    return {
      base: [],
      allCommandScopes: {},
      selectedCommandScopes: {},
      resolved: [],
      unknownCommands: commands ?? [],
    };
  }

  const selectedCommandScopes: Record<string, string[]> = {};
  const unknownCommands: string[] = [];

  for (const cmd of commands ?? []) {
    if (cmd in entry.commands) {
      selectedCommandScopes[cmd] = entry.commands[cmd];
    } else {
      unknownCommands.push(cmd);
    }
  }

  const resolved = resolveScopes(provider, product, commands);
  return {
    base: entry.base,
    allCommandScopes: entry.commands,
    selectedCommandScopes,
    resolved,
    unknownCommands,
  };
}
