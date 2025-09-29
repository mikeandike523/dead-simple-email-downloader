// pages/api/outlook/folders.ts
import { withAuth } from "@/server/withAuth";
import { NextApiResponse } from "next";
import { AuthedNextApiRequest } from "@/server/withAuth";
import { callGraphJSON } from "@/server/msgraph";

/** ──────────────────────────────────────────────────────────────
 * Types (response shape)
 * ──────────────────────────────────────────────────────────────*/

/** Recursive node in the folder hierarchy */
export interface ApiFolderNode {
  id: string;
  name: string;
  hidden: boolean;
  parentId?: string;          // parentFolderId from Graph
  children: ApiFolderNode[];  // recursion
}

/** Forest = list of roots (always an array, even if length === 1) */
export type ApiFolderForest = ApiFolderNode[];

/** Minimal Graph shape we need for traversal */
type GraphMailFolder = {
  id: string;
  displayName: string;
  parentFolderId?: string;
  isHidden?: boolean;
};

type GraphListResponse<T> = {
  value?: T[];
  "@odata.nextLink"?: string;
};

/** ──────────────────────────────────────────────────────────────
 * Helpers
 * ──────────────────────────────────────────────────────────────*/

function normalizeRouteFromNextLink(nextLink: string): string {
  const u = nextLink.startsWith("http")
    ? new URL(nextLink)
    : new URL(nextLink, "https://graph.microsoft.com/v1.0/");
  return u.pathname.replace(/^\/+/, "") + (u.search || "");
}

async function graphGetAll<T>(openidSub: string, route: string): Promise<T[]> {
  const all: T[] = [];
  let next: string | null = route;

  while (next) {
    const res = await callGraphJSON({ openidSub, route: next });
    if (!res.ok) throw new Error(`Graph GET failed for ${next}`);
    const data = (res.data || {}) as GraphListResponse<T>;
    if (Array.isArray(data.value)) all.push(...data.value);
    next = data["@odata.nextLink"]
      ? normalizeRouteFromNextLink(data["@odata.nextLink"])
      : null;
  }
  return all;
}

/** Recursively enumerate all folders starting from root children */
async function enumerateAllFolders(
  openidSub: string
): Promise<GraphMailFolder[]> {
  const SELECT = "$select=id,displayName,parentFolderId,isHidden";
  const TOP = "$top=100";
  const INCLUDE = "includeHiddenFolders=true";

  const rootChildren = await graphGetAll<GraphMailFolder>(
    openidSub,
    `me/mailFolders?${INCLUDE}&${SELECT}&${TOP}`
  );

  const all: GraphMailFolder[] = [...rootChildren];
  const queue = [...rootChildren.map((f) => f.id)];
  const seen = new Set(queue);

  while (queue.length) {
    const parentId = queue.shift()!;
    const children = await graphGetAll<GraphMailFolder>(
      openidSub,
      `me/mailFolders/${parentId}/childFolders?${INCLUDE}&${SELECT}&${TOP}`
    );
    for (const c of children) {
      if (!seen.has(c.id)) {
        seen.add(c.id);
        all.push(c);
        queue.push(c.id);
      }
    }
  }
  return all;
}

/** Build a parentFolderId-based hierarchy (forest) */
function buildFolderForest(flat: GraphMailFolder[]): ApiFolderForest {
  const byId = new Map<string, ApiFolderNode>();

  // Instantiate nodes
  for (const f of flat) {
    byId.set(f.id, {
      id: f.id,
      name: f.displayName,
      hidden: !!f.isHidden,
      parentId: f.parentFolderId,
      children: [],
    });
  }

  // Link children or collect roots
  const roots: ApiFolderNode[] = [];
  for (const node of byId.values()) {
    if (node.parentId && byId.has(node.parentId)) {
      byId.get(node.parentId)!.children.push(node);
    } else {
      roots.push(node);
    }
  }

  // Optional: stable sort by name at every level
  const alpha = (a: ApiFolderNode, b: ApiFolderNode) =>
    a.name.localeCompare(b.name, undefined, { sensitivity: "base" });

  roots.sort(alpha);
  const stack = [...roots];
  while (stack.length) {
    const n = stack.pop()!;
    n.children.sort(alpha);
    for (const c of n.children) stack.push(c);
  }

  return roots;
}

/** ──────────────────────────────────────────────────────────────
 * Handler
 * ──────────────────────────────────────────────────────────────*/
const handler = async (req: AuthedNextApiRequest, res: NextApiResponse) => {
  try {
    const openidSub = req.user.sub;

    // Enumerate every folder (including hidden)
    const folders = await enumerateAllFolders(openidSub);

    // Build and return a forest of roots
    const forest = buildFolderForest(folders);

    return res.status(200).json(forest);
  } catch (err: any) {
    return res
      .status(502)
      .json({ error: "Failed to enumerate folders", detail: String(err?.message || err) });
  }
};

export default withAuth(handler);
