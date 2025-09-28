import { dbQuery } from "./db";
import { sqlUtcTimestampToDate } from "../utils/time-and-date";

/**
 * Calls the microsoft graph token endpoint and gets a new access token
 * and saves in database
 *
 * @param openidSub
 */
async function getNewAccessToken(openidSub: string) {}

async function checkAccessToken(openidSub: string) {
    
}

/**
 *
 * Ensures that the access token stored in the database
 * is fresh for at least `minMinutesRemaining` minutes.
 *
 * @param sub
 * @param minMinutesRemaining
 */
export async function ensureAccessToken(
  openidSub: string,
  minMinutesRemaining = 30
) {
  const accessTokensResult = await dbQuery(
    `
SELECT access_token, expires_at from access_tokens WHERE openid_sub = ?
    `,
    [openidSub]
  );

  // If no tokens yet, then we know we need to call getNewAccessToken
  if (accessTokensResult.length === 0) {
    return await getNewAccessToken(openidSub);
  }

  // We know accessTokens.length === 1 due to unique constrain over openid_sub
    const accessTokenData = accessTokensResult[0];
    const expiresAt = sqlUtcTimestampToDate(accessTokenData.expires_at);
    const now = new Date();
    const remainingMinutes = (expiresAt.getTime() - now.getTime()) / 60000;
    // If we don't have enough time left, then we need to call getNewAccessToken
    if (remainingMinutes <= minMinutesRemaining) {
      return await getNewAccessToken(openidSub);
    }

    // At this point, we now need to touch the graph endpoint to make sure the token
    // we have is good, and if not, then we need to call getNewAccessToken



}
