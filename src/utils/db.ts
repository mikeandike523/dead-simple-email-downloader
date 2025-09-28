// lib/db.ts
// npm i mysql2
import mysql, { RowDataPacket, ResultSetHeader } from 'mysql2/promise';

/**
 * Values you can pass as SQL parameters.
 * Matches what mysql2 accepts for positional args (Array) or named args (Record).
 */
export type SqlPrimitive = string | number | boolean | Date | Buffer | null;
export type SqlParams =
  | ReadonlyArray<SqlPrimitive>
  | Readonly<Record<string, SqlPrimitive>>;

/**
 * The "write" result shape for INSERT / UPDATE / DELETE.
 * `changedRows` is present for UPDATE on some servers; it's optional in types.
 */
export interface ExecResult {
  affectedRows: number;
  insertId: number;       // 0 when not applicable (e.g., UPDATE/DELETE)
  warningStatus: number;  // 0 if no warnings
  changedRows?: number;   // may be undefined if server/statement doesn't provide it
}

/**
 * NOTE ON mysql2 RETURN TUPLE:
 * mysql2/promise always resolves `pool.query(...)` to a tuple:
 *
 *   [result, fields] = await pool.query(...)
 *
 * Where:
 *  - For SELECT/SHOW/DESCRIBE: `result` is an array of row objects (RowDataPacket[]).
 *  - For INSERT/UPDATE/DELETE:  `result` is a ResultSetHeader (metadata).
 *  - `fields` is an array of FieldPacket (column metadata) and is rarely needed
 *    in normal app code, so we intentionally ignore it in these helpers.
 */

declare global {
  // Keep a single pool alive during Next.js dev HMR.
  // In production this assignment is harmless.
  // eslint-disable-next-line no-var
  var _mysqlPool: mysql.Pool | undefined;
}

export const pool: mysql.Pool =
  global._mysqlPool ??
  mysql.createPool({
    host: process.env.MYSQL_HOST!,
    user: process.env.MYSQL_USER!,
    password: process.env.MYSQL_PASSWORD!,
    database: process.env.MYSQL_DATABASE!,
    waitForConnections: true,
    connectionLimit: 10,
    queueLimit: 0,
    enableKeepAlive: true,
    keepAliveInitialDelay: 0,
  });

if (process.env.NODE_ENV !== 'production') {
  global._mysqlPool = pool;
}

/**
 * Run a row-returning query (SELECT/SHOW/DESCRIBE).
 * Always returns an array of row objects of type T.
 *
 * Example:
 *   const rows = await dbQuery<{ id: number; email: string }>(
 *     'SELECT id, email FROM users WHERE active = ?',
 *     [1]
 *   );
 */
export async function dbQuery<T extends RowDataPacket>(
  sql: string,
  params?: SqlParams
): Promise<T[]> {
  const [rows] = await pool.query<T[]>(sql, params as SqlParams | undefined);
  return rows;
}

/**
 * Run a mutation (INSERT/UPDATE/DELETE).
 * Always returns normalized write metadata (ExecResult).
 *
 * Example (INSERT):
 *   const res = await dbExec(
 *     'INSERT INTO oauth_tokens (openid_sub, refresh_token) VALUES (?, ?)',
 *     [sub, token]
 *   );
 *   // res.insertId, res.affectedRows, res.warningStatus
 *
 * Example (UPDATE):
 *   const res = await dbExec(
 *     'UPDATE oauth_tokens SET refresh_token = ? WHERE openid_sub = ?',
 *     [newToken, sub]
 *   );
 *   // res.affectedRows, res.changedRows (optional), res.warningStatus
 */
export async function dbExec(
  sql: string,
  params?: SqlParams
): Promise<ExecResult> {
  const [resultHeader] = await pool.query<ResultSetHeader>(sql, params as SqlParams | undefined);

  // `changedRows` is not in ResultSetHeader typings but is provided by some servers.
  const maybeChanged = (resultHeader as ResultSetHeader & { changedRows?: number }).changedRows;

  return {
    affectedRows: resultHeader.affectedRows,
    insertId: resultHeader.insertId,
    warningStatus: resultHeader.warningStatus,
    changedRows: typeof maybeChanged === 'number' ? maybeChanged : undefined,
  };
}
