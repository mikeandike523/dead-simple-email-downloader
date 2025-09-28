// src/server/withAuthSsr.ts
import type {
  GetServerSideProps,
  GetServerSidePropsContext,
  GetServerSidePropsResult,
} from "next";
import { getAuth, type AuthUser } from "./auth";

export function withAuthSsr(
  gssp?: (
    ctx: GetServerSidePropsContext,
    user: AuthUser
  ) => Promise<GetServerSidePropsResult<any>>
): GetServerSideProps<any> {
  return async (ctx) => {
    const user = await getAuth(ctx.req as any);
    if (!user) {
      return {
        redirect: {
          destination: "/login?next=" + encodeURIComponent(ctx.resolvedUrl ?? "/"),
          permanent: false,
        },
      };
    }

    ctx.res.setHeader?.("Cache-Control", "no-store");

    if (!gssp) {
      return { props: { user: user as AuthUser } };
    }

    const result = await gssp(ctx, user);

    if ("redirect" in result || "notFound" in result) return result;

    const baseProps = (result.props ?? {}) as Record<string, unknown>;
    return {
      props: {
        ...baseProps,
        user: user as AuthUser,
      },
    };
  };
}