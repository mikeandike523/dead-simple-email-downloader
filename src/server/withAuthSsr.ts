// src/server/withAuthSsr.ts
import type { GetServerSideProps, GetServerSidePropsContext, GetServerSidePropsResult } from "next";
import { getAuth, type AuthUser } from "./auth";

/**
 * Protect getServerSideProps. Injects `user` into props.
 * On failure, redirect to your login page or return 401-ish page.
 */
export function withAuthSsr<P extends { user: AuthUser } = any>(
  gssp: (ctx: GetServerSidePropsContext, user: AuthUser) => Promise<GetServerSidePropsResult<P>>
): GetServerSideProps<P> {
  return async (ctx) => {
    // Reuse the same verifier (NextApiRequest-compatible enough for headers/cookies)
    const user = await getAuth(ctx.req as any);
    if (!user) {
      return {
        redirect: {
          destination: "/login?next=" + encodeURIComponent(ctx.resolvedUrl),
          permanent: false,
        },
      };
    }
    return gssp(ctx, user);
  };
}