import { Hono } from 'hono';
import type { AppContextEnv, Bindings } from './types';
import { attachUser } from './lib/auth';
import { authRoutes } from './routes/auth';
import { apiRoutes } from './routes/api';
import { paperRoutes } from './routes/papers';
import { omrRoutes } from './routes/omr';
import { quizRoutes } from './routes/quiz';
import { bankApiRoutes, bankPageRoutes } from './routes/bank';
import { moderationRoutes } from './routes/moderation';
import { adminRoutes } from './routes/admin';
import { runAiGenerationCycle } from './services/ai-generator';
import { renderPageLayout } from './views/layout';

export function createApp() {
  const app = new Hono<AppContextEnv>();

  // Global security headers
  app.use('*', async (c, next) => {
    await next();
    c.res.headers.set('X-Content-Type-Options', 'nosniff');
    c.res.headers.set('X-Frame-Options', 'SAMEORIGIN');
    c.res.headers.set('Referrer-Policy', 'strict-origin-when-cross-origin');
  });

  // Attach authenticated user from signed D1 session cookie
  app.use('*', attachUser);

  // Mount all route modules
  app.route('/', authRoutes);
  app.route('/api', apiRoutes);
  app.route('/', paperRoutes);
  app.route('/', omrRoutes);
  app.route('/quiz', quizRoutes);
  app.route('/', bankPageRoutes);
  app.route('/api/v1/bank', bankApiRoutes);
  app.route('/api/v1/admin/bank', moderationRoutes);
  app.route('/admin', adminRoutes);

  app.notFound((c) => {
    if (c.req.path.startsWith('/api/')) {
      return c.json({ error: 'Not found' }, 404);
    }
    return c.html(
      renderPageLayout(
        { title: 'পৃষ্ঠাটি পাওয়া যায়নি (৪০৪)', user: c.get('user') },
        `<section class="auth-section"><div class="container auth-card" style="text-align:center;">
          <span class="badge-pill">404</span>
          <h1 class="mt-2">পৃষ্ঠাটি খুঁজে পাওয়া যায়নি</h1>
          <p class="muted">আপনি যে ঠিকানায় যেতে চাইছেন তা সরানো হয়েছে বা ভুল।</p>
          <div class="row-actions mt-3" style="justify-content:center;">
            <a href="/" class="btn btn-primary">হোমে ফিরে যান</a>
            <a href="/generate" class="btn btn-outline">দ্রুত প্রশ্ন তৈরি</a>
          </div>
        </div></section>`
      ),
      404
    );
  });

  return app;
}

const app = createApp();

export default {
  fetch: app.fetch,
  async scheduled(_controller: ScheduledController, env: Bindings, ctx: ExecutionContext) {
    ctx.waitUntil(runAiGenerationCycle(env, false));
  },
};
