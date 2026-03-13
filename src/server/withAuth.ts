// src/server/withAuth.ts
import type { NextApiHandler, NextApiRequest, NextApiResponse } from "next";
import { getAuth, type AuthUser } from "./auth";

export interface AuthedNextApiRequest extends NextApiRequest {
  user: AuthUser;
}

export type AuthedHandler<T = unknown> =
  (req: AuthedNextApiRequest, res: NextApiResponse<T>) => void | Promise<void>;

export function withAuth<T = unknown>(handler: AuthedHandler<T>): NextApiHandler<T | { error: string }> {
  return async (req: NextApiRequest, res: NextApiResponse<T | { error: string }>) => {
    const user = await getAuth(req);
    if (!user) {
      if (req.headers.authorization?.startsWith("Bearer ")) {
        res.setHeader("WWW-Authenticate", 'Bearer realm="api", error="invalid_token"');
      }
      return res.status(401).json({ error: "unauthorized" });
    }

    const authedReq = req as AuthedNextApiRequest;
    authedReq.user = user;

    return handler(authedReq, res);
  };
}