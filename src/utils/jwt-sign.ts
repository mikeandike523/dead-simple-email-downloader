// src/utils/jwt-sign.ts
import { SignJWT } from "jose";
import ms, {StringValue} from "ms"; // or implement your own simple parser; or accept seconds

export async function sign(
  claims: Record<string, any>,
  expiresIn: string | number
): Promise<string> {
  const secret = new TextEncoder().encode(process.env.CLI_JWT_SECRET!);
  const now = Math.floor(Date.now() / 1000);
  const exp =
    typeof expiresIn === "number"
      ? now + expiresIn
      : now + Math.floor(ms(expiresIn as StringValue) / 1000);

  return await new SignJWT(claims)
    .setProtectedHeader({ alg: "HS256", typ: "JWT" })
    .setIssuedAt(now)
    .setExpirationTime(exp)
    .sign(secret);
}