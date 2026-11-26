import type { Context, Next } from 'hono';
import type { AppContextEnv } from '../types';

const memoryBuckets = new Map<string, { count: number; resetAt: number }>();

export function rateLimit(maxRequests: number, windowSeconds: number, keyPrefix = 'rl') {
  return async (c: Context<AppContextEnv>, next: Next): Promise<Response | void> => {
    const ip =
      c.req.header('cf-connecting-ip') ||
      c.req.header('x-forwarded-for')?.split(',')[0]?.trim() ||
      '127.0.0.1';
    const user = c.get('user');
    const identity = user?.id || ip;
    const bucketKey = `${keyPrefix}:${c.req.path}:${identity}`;
    const now = Date.now();

    if (c.env.PROSNO_KV) {
      const raw = await c.env.PROSNO_KV.get(bucketKey);
      let state = raw ? (JSON.parse(raw) as { count: number; resetAt: number }) : null;
      if (!state || state.resetAt <= now) {
        state = { count: 1, resetAt: now + windowSeconds * 1000 };
      } else {
        state.count += 1;
      }
      if (state.count > maxRequests) {
        return c.json({ error: 'Rate limit exceeded. Please try again shortly.' }, 429);
      }
      await c.env.PROSNO_KV.put(bucketKey, JSON.stringify(state), {
        expirationTtl: Math.max(60, windowSeconds),
      });
    } else {
      let state = memoryBuckets.get(bucketKey);
      if (!state || state.resetAt <= now) {
        state = { count: 1, resetAt: now + windowSeconds * 1000 };
        memoryBuckets.set(bucketKey, state);
      } else {
        state.count += 1;
      }
      if (state.count > maxRequests) {
        return c.json({ error: 'Rate limit exceeded. Please try again shortly.' }, 429);
      }
    }

    await next();
  };
}
