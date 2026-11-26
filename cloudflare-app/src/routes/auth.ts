import { Hono } from 'hono';
import { getCookie, setCookie, deleteCookie } from 'hono/cookie';
import type { AppContextEnv } from '../types';
import { createSession, destroySession, generatePkcePair, requireTeacher } from '../lib/auth';
import { hashPassword, randomToken, verifyPassword } from '../lib/crypto';
import { getOrCreateProfile } from '../lib/bank-helpers';
import { rateLimit } from '../lib/rate-limit';
import { renderPageLayout } from '../views/layout';
import { escapeHtml } from '../lib/math';

export const authRoutes = new Hono<AppContextEnv>();

function isSafeNextUrl(target: string | undefined): string {
  if (!target || !target.startsWith('/') || target.startsWith('//')) return '/dashboard';
  return target;
}

authRoutes.get('/login', (c) => {
  if (c.get('user')) return c.redirect('/dashboard');
  const nextUrl = isSafeNextUrl(c.req.query('next'));
  const error = c.req.query('error') || '';
  const hasGoogle = Boolean(c.env.GOOGLE_CLIENT_ID && c.env.GOOGLE_CLIENT_SECRET);

  const html = renderPageLayout(
    { title: 'লগইন', user: null },
    `<section class="auth-section"><div class="container auth-card">
      <h1>Prosno.io-তে লগইন করুন</h1>
      <p class="muted">আপনার সেভ করা প্রশ্নপত্র, OMR টেমপ্লেট ও লাইভ কুইজ পরিচালনা করুন।</p>
      ${error ? `<div class="alert error">${escapeHtml(error)}</div>` : ''}
      ${hasGoogle ? `<a href="/auth/google?next=${encodeURIComponent(nextUrl)}" class="btn btn-outline btn-block mb-3">Google দিয়ে চালিয়ে যান</a><div class="divider">অথবা ইমেইল দিয়ে</div>` : ''}
      <form method="POST" action="/login" class="stack-form">
        <input type="hidden" name="next" value="${escapeHtml(nextUrl)}">
        <label>ইমেইল বা ইউজারনেম
          <input type="text" name="email" required placeholder="teacher@example.com">
        </label>
        <label>পাসওয়ার্ড
          <input type="password" name="password" required placeholder="••••••••">
        </label>
        <button type="submit" class="btn btn-primary btn-block">লগইন</button>
      </form>
      <p class="mt-3 text-center">নতুন অ্যাকাউন্ট খুলতে চান? <a href="/register">রেজিস্ট্রেশন করুন</a></p>
    </div></section>`
  );
  return c.html(html);
});

authRoutes.post('/login', rateLimit(15, 60, 'auth_login'), async (c) => {
  let email = '';
  let password = '';
  let nextUrl = '/dashboard';
  const ct = c.req.header('content-type') || '';
  if (ct.includes('application/json')) {
    const body = (await c.req.json().catch(() => ({}))) as Record<string, string>;
    email = (body.email || body.username || '').trim();
    password = body.password || '';
    nextUrl = isSafeNextUrl(body.next);
  } else {
    const form = await c.req.parseBody();
    email = String(form.email || form.username || '').trim();
    password = String(form.password || '');
    nextUrl = isSafeNextUrl(String(form.next || '/dashboard'));
  }

  const userRow = await c.env.DB.prepare(
    'SELECT id, public_uid, username, email, display_name, password_hash, role, is_admin, is_active_user FROM users WHERE LOWER(email) = LOWER(?) OR LOWER(username) = LOWER(?)'
  )
    .bind(email, email)
    .first<{
      id: number;
      public_uid: string;
      username: string;
      email: string;
      display_name: string | null;
      password_hash: string;
      role: string;
      is_admin: number;
      is_active_user: number;
    }>();

  if (!userRow || !userRow.is_active_user || !(await verifyPassword(password, userRow.password_hash))) {
    if (ct.includes('application/json')) {
      return c.json({ error: 'Invalid credentials' }, 401);
    }
    return c.redirect(`/login?error=${encodeURIComponent('ইমেইল অথবা পাসওয়ার্ড সঠিক নয়।')}&next=${encodeURIComponent(nextUrl)}`);
  }

  await c.env.DB.prepare(`UPDATE users SET last_login = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?`)
    .bind(userRow.id)
    .run();
  await createSession(c, userRow.id);

  if (ct.includes('application/json')) {
    return c.json({
      success: true,
      user: {
        id: userRow.public_uid,
        username: userRow.username,
        email: userRow.email,
        display_name: userRow.display_name || userRow.username,
        role: userRow.role,
      },
    });
  }
  return c.redirect(nextUrl);
});

authRoutes.get('/register', (c) => {
  if (c.get('user')) return c.redirect('/dashboard');
  const error = c.req.query('error') || '';
  const html = renderPageLayout(
    { title: 'রেজিস্ট্রেশন', user: null },
    `<section class="auth-section"><div class="container auth-card">
      <h1>নতুন শিক্ষক অ্যাকাউন্ট খুলুন</h1>
      <p class="muted">বিনামূল্যে প্রশ্নপত্র, উত্তরমালা ও OMR তৈরি শুরু করুন।</p>
      ${error ? `<div class="alert error">${escapeHtml(error)}</div>` : ''}
      <form method="POST" action="/register" class="stack-form">
        <label>পূর্ণ নাম
          <input type="text" name="display_name" required placeholder="যেমন: মো. করিম উদ্দিন">
        </label>
        <label>ইমেইল
          <input type="email" name="email" required placeholder="teacher@example.com">
        </label>
        <label>পাসওয়ার্ড (কমপক্ষে ৬ অক্ষর)
          <input type="password" name="password" minlength="6" required placeholder="••••••••">
        </label>
        <button type="submit" class="btn btn-primary btn-block">অ্যাকাউন্ট তৈরি করুন</button>
      </form>
      <p class="mt-3 text-center">ইতিমধ্যে অ্যাকাউন্ট আছে? <a href="/login">লগইন করুন</a></p>
    </div></section>`
  );
  return c.html(html);
});

authRoutes.post('/register', rateLimit(10, 60, 'auth_register'), async (c) => {
  const ct = c.req.header('content-type') || '';
  let email = '';
  let password = '';
  let displayName = '';

  if (ct.includes('application/json')) {
    const body = (await c.req.json().catch(() => ({}))) as Record<string, string>;
    email = (body.email || '').trim().toLowerCase();
    password = body.password || '';
    displayName = (body.display_name || body.name || '').trim();
  } else {
    const form = await c.req.parseBody();
    email = String(form.email || '').trim().toLowerCase();
    password = String(form.password || '');
    displayName = String(form.display_name || form.name || '').trim();
  }

  if (!email || !email.includes('@') || password.length < 6) {
    if (ct.includes('application/json')) return c.json({ error: 'Valid email and password (min 6 chars) required.' }, 400);
    return c.redirect(`/register?error=${encodeURIComponent('সঠিক ইমেইল ও কমপক্ষে ৬ অক্ষরের পাসওয়ার্ড দিন।')}`);
  }

  const existing = await c.env.DB.prepare('SELECT id FROM users WHERE LOWER(email) = LOWER(?)').bind(email).first();
  if (existing) {
    if (ct.includes('application/json')) return c.json({ error: 'Email already registered.' }, 409);
    return c.redirect(`/register?error=${encodeURIComponent('এই ইমেইলটি ইতিমধ্যে নিবন্ধিত।')}`);
  }

  const baseUsername = email.split('@')[0].replace(/[^a-zA-Z0-9_]/g, '').slice(0, 20) || 'teacher';
  const username = `${baseUsername}_${randomToken(3)}`;
  const publicUid = crypto.randomUUID();
  const pwHash = await hashPassword(password);

  const insertRes = await c.env.DB.prepare(
    `INSERT INTO users (public_uid, username, email, display_name, password_hash, role, is_admin, is_active_user)
     VALUES (?, ?, ?, ?, ?, 'teacher', 0, 1)`
  )
    .bind(publicUid, username, email, displayName || baseUsername, pwHash)
    .run();

  const newUserId = Number(insertRes.meta.last_row_id);
  await getOrCreateProfile(c.env.DB, publicUid, displayName || baseUsername);
  await createSession(c, newUserId);

  if (ct.includes('application/json')) {
    return c.json({ success: true, user: { id: publicUid, email, display_name: displayName || baseUsername } }, 201);
  }
  return c.redirect('/dashboard');
});

authRoutes.get('/logout', async (c) => {
  await destroySession(c);
  return c.redirect('/');
});

authRoutes.post('/logout', async (c) => {
  await destroySession(c);
  return c.json({ success: true });
});

authRoutes.get('/auth/google', async (c) => {
  if (!c.env.GOOGLE_CLIENT_ID || !c.env.GOOGLE_CLIENT_SECRET) {
    return c.redirect(`/login?error=${encodeURIComponent('Google OAuth কনফিগার করা হয়নি।')}`);
  }
  const { verifier, challenge } = await generatePkcePair();
  const state = randomToken(16);
  const nextUrl = isSafeNextUrl(c.req.query('next'));
  const redirectUri = `${new URL(c.req.url).origin}/auth/callback`;

  setCookie(c, 'g_oauth_state', JSON.stringify({ state, verifier, nextUrl }), {
    httpOnly: true,
    sameSite: 'Lax',
    path: '/',
    maxAge: 600,
  });

  const authUrl = new URL('https://accounts.google.com/o/oauth2/v2/auth');
  authUrl.searchParams.set('client_id', c.env.GOOGLE_CLIENT_ID);
  authUrl.searchParams.set('redirect_uri', redirectUri);
  authUrl.searchParams.set('response_type', 'code');
  authUrl.searchParams.set('scope', 'openid email profile');
  authUrl.searchParams.set('state', state);
  authUrl.searchParams.set('code_challenge', challenge);
  authUrl.searchParams.set('code_challenge_method', 'S256');
  return c.redirect(authUrl.toString());
});

authRoutes.get('/auth/callback', async (c) => {
  const code = c.req.query('code');
  const state = c.req.query('state');
  const cookieRaw = getCookie(c, 'g_oauth_state');
  deleteCookie(c, 'g_oauth_state', { path: '/' });

  if (!code || !state || !cookieRaw || !c.env.GOOGLE_CLIENT_ID || !c.env.GOOGLE_CLIENT_SECRET) {
    return c.redirect('/login?error=Google+auth+failed');
  }
  let saved: { state: string; verifier: string; nextUrl: string };
  try {
    saved = JSON.parse(cookieRaw);
  } catch {
    return c.redirect('/login?error=Invalid+OAuth+state');
  }
  if (saved.state !== state) {
    return c.redirect('/login?error=State+mismatch');
  }

  const redirectUri = `${new URL(c.req.url).origin}/auth/callback`;
  const tokenResp = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      code,
      client_id: c.env.GOOGLE_CLIENT_ID,
      client_secret: c.env.GOOGLE_CLIENT_SECRET,
      redirect_uri: redirectUri,
      grant_type: 'authorization_code',
      code_verifier: saved.verifier,
    }),
  });
  if (!tokenResp.ok) return c.redirect('/login?error=OAuth+token+exchange+failed');
  const tokenJson = (await tokenResp.json()) as { access_token?: string };
  if (!tokenJson.access_token) return c.redirect('/login?error=No+access+token');

  const userInfoResp = await fetch('https://www.googleapis.com/oauth2/v3/userinfo', {
    headers: { Authorization: `Bearer ${tokenJson.access_token}` },
  });
  if (!userInfoResp.ok) return c.redirect('/login?error=Failed+to+fetch+Google+profile');
  const profile = (await userInfoResp.json()) as { sub: string; email: string; name?: string };
  const email = (profile.email || '').toLowerCase();
  if (!email) return c.redirect('/login?error=No+email+from+Google');

  let userRow = await c.env.DB.prepare('SELECT id, public_uid FROM users WHERE google_sub = ? OR LOWER(email) = LOWER(?)')
    .bind(profile.sub, email)
    .first<{ id: number; public_uid: string }>();

  if (!userRow) {
    const publicUid = crypto.randomUUID();
    const base = email.split('@')[0].replace(/[^a-zA-Z0-9_]/g, '').slice(0, 20) || 'teacher';
    const username = `${base}_${randomToken(3)}`;
    const randomPw = await hashPassword(randomToken(24));
    const ins = await c.env.DB.prepare(
      `INSERT INTO users (public_uid, username, email, display_name, password_hash, auth_provider, google_sub, role, is_admin, is_active_user)
       VALUES (?, ?, ?, ?, ?, 'google', ?, 'teacher', 0, 1)`
    )
      .bind(publicUid, username, email, profile.name || base, randomPw, profile.sub)
      .run();
    userRow = { id: Number(ins.meta.last_row_id), public_uid: publicUid };
    await getOrCreateProfile(c.env.DB, publicUid, profile.name || base);
  }

  await createSession(c, userRow.id);
  return c.redirect(saved.nextUrl || '/dashboard');
});

authRoutes.get('/api/auth/me', (c) => {
  const user = c.get('user');
  if (!user) return c.json({ authenticated: false, user: null });
  return c.json({ authenticated: true, user });
});

authRoutes.put('/api/auth/branding', requireTeacher, async (c) => {
  const user = c.get('user')!;
  const body = (await c.req.json().catch(() => ({}))) as Record<string, string>;
  await getOrCreateProfile(c.env.DB, user.id, user.display_name);
  await c.env.DB.prepare(
    `UPDATE teacher_profiles
     SET institute_name = ?, institute_subtitle = ?, logo_url = ?, watermark_text = ?, default_font = ?,
         updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
     WHERE user_id = ?`
  )
    .bind(
      (body.institute_name || '').slice(0, 140),
      (body.institute_subtitle || '').slice(0, 180),
      (body.logo_url || '').slice(0, 100000),
      (body.watermark_text || '').slice(0, 100),
      body.default_font || 'hind',
      user.id
    )
    .run();
  return c.json({ success: true });
});

authRoutes.post('/api/auth/bootstrap-admin', async (c) => {
  const body = (await c.req.json().catch(() => ({}))) as Record<string, string>;
  const adminCountRow = await c.env.DB.prepare("SELECT COUNT(*) as cnt FROM users WHERE role = 'admin' OR is_admin = 1").first<{ cnt: number }>();
  const hasAdmin = (adminCountRow?.cnt || 0) > 0;

  if (hasAdmin) {
    if (!c.env.ADMIN_BOOTSTRAP_SECRET || body.secret !== c.env.ADMIN_BOOTSTRAP_SECRET) {
      return c.json({ error: 'Admin already exists' }, 403);
    }
  }

  const username = (body.username || 'admin').trim();
  const email = (body.email || 'admin@prosno.io').trim().toLowerCase();
  const password = body.password || '';
  if (password.length < 6) return c.json({ error: 'Password must be at least 6 characters' }, 400);

  const pwHash = await hashPassword(password);
  const publicUid = crypto.randomUUID();
  await c.env.DB.prepare(
    `INSERT INTO users (public_uid, username, email, display_name, password_hash, role, is_admin, is_active_user)
     VALUES (?, ?, ?, 'Administrator', ?, 'admin', 1, 1)`
  )
    .bind(publicUid, username, email, pwHash)
    .run();

  return c.json({ success: true, username, email }, 201);
});
