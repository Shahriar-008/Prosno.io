import { DatabaseSync } from 'node:sqlite';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import type { Bindings } from '../../src/types';

class NodeSqlitePreparedStatement {
  private bound: unknown[] = [];

  constructor(private db: DatabaseSync, private sql: string) {}

  bind(...values: unknown[]) {
    this.bound = values.map((v) => (v === undefined ? null : v));
    return this;
  }

  async first<T = Record<string, unknown>>(colName?: string): Promise<T | null> {
    const stmt = this.db.prepare(this.sql);
    const row = stmt.get(...(this.bound as never[])) as Record<string, unknown> | undefined;
    if (!row) return null;
    if (colName) return (row[colName] as T) ?? null;
    return row as T;
  }

  async all<T = Record<string, unknown>>(): Promise<{ results: T[]; success: boolean; meta: Record<string, unknown> }> {
    const stmt = this.db.prepare(this.sql);
    const rows = stmt.all(...(this.bound as never[])) as T[];
    return { results: rows, success: true, meta: {} };
  }

  async run(): Promise<{ success: boolean; meta: { last_row_id: number; changes: number } }> {
    const stmt = this.db.prepare(this.sql);
    const info = stmt.run(...(this.bound as never[]));
    return {
      success: true,
      meta: {
        last_row_id: Number(info.lastInsertRowid || 0),
        changes: Number(info.changes || 0),
      },
    };
  }

  async raw<T = unknown[]>(): Promise<T[]> {
    const stmt = this.db.prepare(this.sql);
    const rows = stmt.all(...(this.bound as never[])) as Record<string, unknown>[];
    return rows.map((r) => Object.values(r) as T);
  }
}

export function createTestD1(): { d1: D1Database; sqlite: DatabaseSync } {
  const sqlite = new DatabaseSync(':memory:');
  const mig1 = readFileSync(resolve(__dirname, '../../migrations/0001_initial.sql'), 'utf-8');
  const mig2 = readFileSync(resolve(__dirname, '../../migrations/0002_seed_nctb.sql'), 'utf-8');
  sqlite.exec(mig1);
  sqlite.exec(mig2);

  const d1 = {
    prepare(sql: string) {
      return new NodeSqlitePreparedStatement(sqlite, sql);
    },
    async batch(statements: NodeSqlitePreparedStatement[]) {
      sqlite.exec('BEGIN');
      try {
        const results = [];
        for (const s of statements) {
          results.push(await s.run());
        }
        sqlite.exec('COMMIT');
        return results;
      } catch (err) {
        sqlite.exec('ROLLBACK');
        throw err;
      }
    },
    async exec(sql: string) {
      sqlite.exec(sql);
      return { count: 1, duration: 0 };
    },
    async dump() {
      return new ArrayBuffer(0);
    },
  };

  return { d1: d1 as unknown as D1Database, sqlite };
}

export function createTestEnv(overrides?: Partial<Bindings>): Bindings {
  const { d1 } = createTestD1();
  return {
    DB: d1,
    SESSION_SECRET: 'test-session-secret-123456',
    ENCRYPTION_KEY: 'test-encryption-key-123456',
    ADMIN_BOOTSTRAP_SECRET: 'bootstrap-secret',
    ...overrides,
  };
}

export function extractCookies(resp: Response): string {
  const getSetCookie = (resp.headers as unknown as { getSetCookie?: () => string[] }).getSetCookie;
  const rawList = getSetCookie ? getSetCookie.call(resp.headers) : [];
  if (rawList.length > 0) {
    return rawList.map((c) => c.split(';')[0]).join('; ');
  }
  const single = resp.headers.get('set-cookie');
  return single ? single.split(';')[0] : '';
}
