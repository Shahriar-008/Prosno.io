import { describe, it, expect } from 'vitest';
import { createApp } from '../src/index';
import { createTestEnv, extractCookies } from './helpers/d1-sqlite';

describe('Auth & NCTB Curriculum APIs', () => {
  it('registers, logs in, checks /api/auth/me, and guards admin routes', async () => {
    const app = createApp();
    const env = createTestEnv();

    // Register teacher
    const regResp = await app.fetch(
      new Request('http://localhost/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          display_name: 'Karim Teacher',
          email: 'karim@example.com',
          password: 'password123',
        }),
      }),
      env
    );
    expect(regResp.status).toBe(201);
    const cookie = extractCookies(regResp);
    expect(cookie).toContain('prosno_session=');

    // Check /api/auth/me
    const meResp = await app.fetch(
      new Request('http://localhost/api/auth/me', { headers: { Cookie: cookie } }),
      env
    );
    const me = (await meResp.json()) as { authenticated: boolean; user: { email: string; role: string } };
    expect(me.authenticated).toBe(true);
    expect(me.user.email).toBe('karim@example.com');
    expect(me.user.role).toBe('teacher');

    // Teacher cannot access admin moderation
    const modResp = await app.fetch(
      new Request('http://localhost/api/v1/admin/bank/stats', { headers: { Cookie: cookie } }),
      env
    );
    expect(modResp.status).toBe(403);

    // Bootstrap admin & login
    const bootResp = await app.fetch(
      new Request('http://localhost/api/auth/bootstrap-admin', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: 'admin', email: 'admin@prosno.io', password: 'adminpassword' }),
      }),
      env
    );
    expect(bootResp.status).toBe(201);
  });

  it('serves seeded NCTB classes, subjects, chapters, and stats', async () => {
    const app = createApp();
    const env = createTestEnv();

    const classesResp = await app.fetch(new Request('http://localhost/api/classes'), env);
    expect(classesResp.status).toBe(200);
    const classes = (await classesResp.json()) as Array<{ id: number; name: string }>;
    expect(classes.length).toBe(10);

    const subjResp = await app.fetch(new Request(`http://localhost/api/subjects/${classes[8].id}`), env);
    const subjects = (await subjResp.json()) as Array<{ id: number; name: string }>;
    expect(subjects.length).toBeGreaterThan(0);

    const chapResp = await app.fetch(new Request(`http://localhost/api/chapters/${subjects[0].id}`), env);
    const chapters = (await chapResp.json()) as Array<{ id: number }>;
    expect(chapters.length).toBeGreaterThan(0);

    const statsResp = await app.fetch(new Request('http://localhost/api/stats'), env);
    const stats = (await statsResp.json()) as { classes: number; questions: number };
    expect(stats.classes).toBe(10);
    expect(stats.questions).toBeGreaterThanOrEqual(20);
  });
});
