import type { Context, Next } from 'hono';
import { getCookie, setCookie, deleteCookie } from 'hono/cookie';
import type { AppContextEnv, AuthUser } from '../types';
import { hmacSign, hmacVerify, randomToken } from './crypto';

const SESSION_COOKIE = 'prosno_session';
const SESSION_TTL_SECONDS = 60 * 60 * 24 * 7; // 7 days

function getSessionSecret(c: Context<AppContextEnv>): string {
  return c.env.SESSION_SECRET || 'prosno-dev-session-secret-change-in-prod';
}

export async function createSession(c: Context<AppContextEnv>, numericUserId: number): Promise<string> {
  const sessionId = randomToken(24);
  const expiresAt = new Date(Date.now() + SESSION_TTL_SECONDS * 1000).toISOString();

  await c.env.DB.prepare(
    'INSERT INTO sessions (id, user_id, expires_at) VALUES (?, ?, ?)'
  )
    .bind(sessionId, numericUserId, expiresAt)
    .run();

  const sig = await hmacSign(sessionId, getSessionSecret(c));
  const cookieVal = `${sessionId}.${sig}`;
  const isHttps = new URL(c.req.url).protocol === 'https:';

  setCookie(c, SESSION_COOKIE, cookieVal, {
    httpOnly: true,
    secure: isHttps,
    sameSite: 'Lax',
    path: '/',
    maxAge: SESSION_TTL_SECONDS,
  });

  return sessionId;
}

export async function destroySession(c: Context<AppContextEnv>): Promise<void> {
  const raw = getCookie(c, SESSION_COOKIE);
  if (raw) {
    const [sessionId] = raw.split('.');
    if (sessionId) {
      await c.env.DB.prepare('DELETE FROM sessions WHERE id = ?').bind(sessionId).run();
    }
  }
  deleteCookie(c, SESSION_COOKIE, { path: '/' });
}

export async function resolveSessionUser(c: Context<AppContextEnv>): Promise<AuthUser | null> {
  const raw = getCookie(c, SESSION_COOKIE);
  if (!raw) return null;

  const dotIdx = raw.indexOf('.');
  if (dotIdx <= 0) return null;
  const sessionId = raw.slice(0, dotIdx);
  const sig = raw.slice(dotIdx + 1);

  const valid = await hmacVerify(sessionId, sig, getSessionSecret(c));
  if (!valid) return null;

  const row = await c.env.DB.prepare(
    `SELECT u.id, u.public_uid, u.username, u.email, u.display_name, u.role, u.is_admin, u.is_active_user, s.expires_at
     FROM sessions s
     JOIN users u ON u.id = s.user_id
     WHERE s.id = ?`
  )
    .bind(sessionId)
    .first<{
      id: number;
      public_uid: string;
      username: string;
      email: string;
      display_name: string | null;
      role: string;
      is_admin: number;
      is_active_user: number;
      expires_at: string;
    }>();

  if (!row || !row.is_active_user) return null;
  if (new Date(row.expires_at).getTime() < Date.now()) {
    await c.env.DB.prepare('DELETE FROM sessions WHERE id = ?').bind(sessionId).run();
    return null;
  }

  return {
    id: row.public_uid,
    numeric_id: row.id,
    username: row.username,
    email: row.email,
    display_name: row.display_name || row.username,
    role: (row.role as AuthUser['role']) || 'teacher',
    is_admin: row.role === 'admin' || row.is_admin === 1,
  };
}

export async function attachUser(c: Context<AppContextEnv>, next: Next): Promise<Response | void> {
  const user = await resolveSessionUser(c);
  c.set('user', user);
  await next();
}

export async function requireTeacher(c: Context<AppContextEnv>, next: Next): Promise<Response | void> {
  const user = c.get('user');
  if (!user) {
    if (c.req.path.startsWith('/api/') || c.req.header('accept')?.includes('application/json')) {
      return c.json({ error: 'Authentication required' }, 401);
    }
    return c.redirect(`/login?next=${encodeURIComponent(c.req.path)}`);
  }
  await next();
}

export async function requireAdmin(c: Context<AppContextEnv>, next: Next): Promise<Response | void> {
  const user = c.get('user');
  if (!user || !user.is_admin) {
    if (c.req.path.startsWith('/api/') || c.req.header('accept')?.includes('application/json')) {
      return c.json({ error: 'Admin access required' }, 403);
    }
    return c.redirect('/admin/login');
  }
  await next();
}

export async function requireEditorOrAdmin(c: Context<AppContextEnv>, next: Next): Promise<Response | void> {
  const user = c.get('user');
  if (!user || (user.role !== 'admin' && user.role !== 'editor' && !user.is_admin)) {
    if (c.req.path.startsWith('/api/') || c.req.header('accept')?.includes('application/json')) {
      return c.json({ error: 'Editor or Admin access required' }, 403);
    }
    return c.redirect('/admin/login');
  }
  await next();
}

export async function generatePkcePair(): Promise<{ verifier: string; challenge: string }> {
  const verifier = randomToken(32);
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier));
  const bytes = new Uint8Array(digest);
  let bin = '';
  for (const b of bytes) bin += String.fromCharCode(b);
  const challenge = btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  return { verifier, challenge };
}
