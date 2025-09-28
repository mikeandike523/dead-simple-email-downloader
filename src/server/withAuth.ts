// src/server/withAuth.ts
import type { NextApiHandler, NextApiRequest, NextApiResponse } from "next";
import { getAuth, type AuthUser } from "./auth";

declare module "next" {
  interface NextApiRequest {
    user?: AuthUser;
  }
}

/**
 * Protect API routes. Attaches req.user on success.
 * Returns 401 with WWW-Authenticate on failure.
 */
export function withAuth(handler: NextApiHandler): NextApiHandler {
  return async (req: NextApiRequest, res: NextApiResponse) => {
    const user = await getAuth(req);
    if (!user) {
      if (req.headers.authorization?.startsWith("Bearer ")) {
        // looks like a CLI attempt, hint Bearer usage
        res.setHeader(
          "WWW-Authenticate",
          'Bearer realm="api", error="invalid_token"'
        );
      }
      return res.status(401).json({ error: "unauthorized" });
    }
    req.user = user;
    return handler(req, res);
  };
}
