// src/server/withAuth.ts
import type { NextApiHandler, NextApiRequest, NextApiResponse } from "next";
import { getAuth, type AuthUser } from "./auth";

export interface AuthedNextApiRequest extends NextApiRequest {
  user: AuthUser;
}

export type AuthedHandler<T = any> =
  (req: AuthedNextApiRequest, res: NextApiResponse<T>) => void | Promise<void>;

export function withAuth<T = any>(handler: AuthedHandler<T>): NextApiHandler<T> {
  return async (req: NextApiRequest, res: NextApiResponse<T>) => {
    const user = await getAuth(req);
    if (!user) {
      if (req.headers.authorization?.startsWith("Bearer ")) {
        res.setHeader("WWW-Authenticate", 'Bearer realm="api", error="invalid_token"');
      }
      return res.status(401).json({ error: "unauthorized" } as any);
    }

    const authedReq = req as AuthedNextApiRequest;
    authedReq.user = user;

    return handler(authedReq, res);
  };
}