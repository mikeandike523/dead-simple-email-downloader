// lib/db.ts
// npm i mysql2
import mysql, { RowDataPacket, ResultSetHeader, PoolConnection } from 'mysql2/promise';

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
  insertId: number; // 0 when not applicable (e.g., UPDATE/DELETE)
  warningStatus: number; // 0 if no warnings
  changedRows?: number; // may be undefined if server/statement doesn't provide it
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
    timezone: 'Z', // ensure UTC, no conversion
    dateStrings: true, // return TIMESTAMP/DATETIME as strings
  });

// Likely extra, but there just to be safe
pool.on('connection', (conn) => {
  conn.query("SET time_zone = '+00:00'");
});

if (process.env.NODE_ENV !== 'production') {
  global._mysqlPool = pool;
}

/**
 * A live transactional connection obtained from pool.getConnection().
 * Any statements that must be in the SAME transaction should use this handle.
 */
export type Tx = mysql.PoolConnection;

export type IsolationLevel =
  | 'READ UNCOMMITTED'
  | 'READ COMMITTED'
  | 'REPEATABLE READ'
  | 'SERIALIZABLE';

/**
 * MySQL error numbers that are safe to retry at the transaction boundary.
 */
const ER_LOCK_DEADLOCK = 1213;
const ER_LOCK_WAIT_TIMEOUT = 1205;

function isRetryableTxError(err: unknown): boolean {
  const code = typeof err === 'object' && err && (err as any).errno;
  return code === ER_LOCK_DEADLOCK || code === ER_LOCK_WAIT_TIMEOUT;
}

/**
 * Run `fn` inside a DB transaction on a single connection.
 * Ensures begin/commit/rollback and always releases the connection.
 *
 * Options:
 *  - isolationLevel: set per-transaction isolation before BEGIN (defaults to server/engine default, typically REPEATABLE READ for InnoDB)
 *  - maxRetries: number of times to retry the WHOLE transaction when we hit a retryable error (deadlock/lock wait timeout). Defaults to 0 (no retry).
 *  - onRetry: optional hook invoked with (attempt, error).
 *
 * Usage:
 *   const result = await withTransaction(async (tx) => {
 *     const rows = await dbQuery<User>('SELECT ... WHERE id=? FOR UPDATE', [id], tx);
 *     await dbExec('UPDATE users SET ... WHERE id=?', [id], tx);
 *     return rows[0];
 *   }, { isolationLevel: 'REPEATABLE READ', maxRetries: 2 });
 */
export async function withTransaction<T>(
  fn: (tx: Tx) => Promise<T>,
  opts?: {
    isolationLevel?: IsolationLevel;
    maxRetries?: number;
    onRetry?: (attempt: number, err: unknown) => void;
    /** If provided, we assume we're inside a transaction and will NOT manage lifecycle */
    connection?: PoolConnection;
  }
): Promise<T> {
  const parentConn = opts?.connection;

  // If we're given a connection, treat this as nested: just run with it.
  if (parentConn) {
    // No SET TRANSACTION / begin / commit / rollback / release here.
    return await fn(parentConn);
  }

  // Top-level: we own lifecycle + retries.
  const maxRetries = Math.max(0, opts?.maxRetries ?? 0);
  let attempt = 0;

  while (true) {
    const conn = await pool.getConnection();
    try {
      if (opts?.isolationLevel) {
        await conn.query(`SET TRANSACTION ISOLATION LEVEL ${opts.isolationLevel}`);
      }

      await conn.beginTransaction();
      const out = await fn(conn);
      await conn.commit();
      return out;
    } catch (err) {
      try { await conn.rollback(); } catch {}

      if (attempt < maxRetries && isRetryableTxError(err)) {
        attempt += 1;
        try { conn.release(); } catch {}
        opts?.onRetry?.(attempt, err);
        const delayMs = 50 + Math.floor(Math.random() * 100) * attempt;
        await new Promise(r => setTimeout(r, delayMs));
        continue;
      }

      throw err;
    } finally {
      try { conn.release(); } catch {}
    }
  }
}
/**
 * Run a row-returning query (SELECT/SHOW/DESCRIBE).
 * If `tx` is provided, executes on that transaction's connection.
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
  params?: SqlParams,
  tx?: Tx
): Promise<T[]> {
  const client: mysql.Pool | mysql.PoolConnection = tx ?? pool;
  const [rows] = await client.query<T[]>(sql, params as SqlParams | undefined);
  return rows;
}

/**
 * Run a mutation (INSERT/UPDATE/DELETE).
 * If `tx` is provided, executes on that transaction's connection.
 * Always returns normalized write metadata (ExecResult).
 *
 * Example (INSERT):
 *   const res = await dbExec(
 *     'INSERT INTO oauth_tokens (openid_sub, refresh_token) VALUES (?, ?)',
 *     [sub, token]
 *   );
 *
 * Example (UPDATE):
 *   const res = await dbExec(
 *     'UPDATE oauth_tokens SET refresh_token = ? WHERE openid_sub = ?',
 *     [newToken, sub]
 *   );
 */
export async function dbExec(
  sql: string,
  params?: SqlParams,
  tx?: Tx
): Promise<ExecResult> {
  const client: mysql.Pool | mysql.PoolConnection = tx ?? pool;
  const [resultHeader] = await client.query<ResultSetHeader>(
    sql,
    params as SqlParams | undefined
  );

  // `changedRows` is not in ResultSetHeader typings but is provided by some servers.
  const maybeChanged = (resultHeader as ResultSetHeader & { changedRows?: number }).changedRows;

  return {
    affectedRows: resultHeader.affectedRows,
    insertId: resultHeader.insertId,
    warningStatus: resultHeader.warningStatus,
    changedRows: typeof maybeChanged === 'number' ? maybeChanged : undefined,
  };
}
