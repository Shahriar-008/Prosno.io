import type { AuthUser } from '../types';
import { escapeHtml } from '../lib/math';

export interface PageLayoutOptions {
  title: string;
  description?: string;
  user?: AuthUser | null;
  extraHead?: string;
  extraScripts?: string;
  activeNav?: string;
}

export function renderPageLayout(opts: PageLayoutOptions, bodyHtml: string): string {
  const user = opts.user;
  const navItem = (href: string, label: string, key: string) =>
    `<a href="${href}" class="nav-link${opts.activeNav === key ? ' active' : ''}">${label}</a>`;

  const authBlock = user
    ? `<div class="nav-user">
        <a href="/dashboard" class="nav-pill">ড্যাশবোর্ড (${escapeHtml(user.display_name)})</a>
        ${user.is_admin ? '<a href="/admin/dashboard" class="nav-pill admin">Admin</a>' : ''}
        <a href="/logout" class="nav-link">লগআউট</a>
      </div>`
    : `<div class="nav-user">
        <a href="/login" class="nav-link">লগইন</a>
        <a href="/register" class="nav-pill primary">ফ্রি শুরু করুন</a>
      </div>`;

  return `<!DOCTYPE html>
<html lang="bn">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${escapeHtml(opts.title)} | Prosno.io</title>
  <meta name="description" content="${escapeHtml(opts.description || 'Prosno.io — বাংলাদেশের শিক্ষক ও কোচিং সেন্টারের জন্য আধুনিক MCQ, CQ, OMR ও লাইভ কুইজ প্ল্যাটফর্ম।')}">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Hind+Siliguri:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/css/app.css">
  ${opts.extraHead || ''}
</head>
<body>
  <header class="site-header">
    <div class="container nav-wrap">
      <a href="/" class="brand">
        <span class="brand-badge">P</span>
        <span>Prosno.io</span>
      </a>
      <nav class="main-nav">
        ${navItem('/generate', 'দ্রুত প্রশ্ন', 'generate')}
        ${navItem('/builder', 'স্মার্ট বিল্ডার', 'builder')}
        ${navItem('/omr-builder', 'OMR ডিজাইনার', 'omr')}
        ${navItem('/bank', 'প্রশ্ন ব্যাংক', 'bank')}
        ${navItem('/quiz/join', 'লাইভ কুইজ', 'quiz')}
      </nav>
      ${authBlock}
    </div>
  </header>

  <main class="main-content">
    ${bodyHtml}
  </main>

  <footer class="site-footer">
    <div class="container footer-grid">
      <div>
        <strong>Prosno.io Edge</strong>
        <p>শিক্ষক ও কোচিং সেন্টারের জন্য ১-ক্লিকে বোর্ড-স্ট্যান্ডার্ড প্রশ্নপত্র, সমাধান, OMR শিট ও লাইভ কুইজ।</p>
      </div>
      <div class="footer-links">
        <a href="/about">আমাদের সম্পর্কে</a>
        <a href="/contact">যোগাযোগ</a>
        <a href="/bank/leaderboard">লিডারবোর্ড</a>
        <a href="/admin/login">অ্যাডমিন</a>
      </div>
    </div>
  </footer>
  ${opts.extraScripts || ''}
</body>
</html>`;
}
