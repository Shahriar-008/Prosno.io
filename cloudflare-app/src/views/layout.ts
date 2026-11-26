import type { AuthUser } from '../types';
import { escapeHtml } from '../lib/math';
import { icon, type IconName } from './icons';

export interface BreadcrumbItem {
  label: string;
  href?: string;
}

export interface PageLayoutOptions {
  title: string;
  description?: string;
  user?: AuthUser | null;
  extraHead?: string;
  extraScripts?: string;
  activeNav?: string;
  breadcrumbs?: BreadcrumbItem[];
}

export function renderPageLayout(opts: PageLayoutOptions, bodyHtml: string): string {
  const user = opts.user;
  const navLinks: Array<{ href: string; label: string; key: string; ic: IconName }> = [
    { href: '/generate', label: 'দ্রুত প্রশ্ন', key: 'generate', ic: 'zap' },
    { href: '/builder', label: 'পেপার বিল্ডার', key: 'builder', ic: 'layers' },
    { href: '/omr-builder', label: 'OMR শিট', key: 'omr', ic: 'grid' },
    { href: '/bank', label: 'প্রশ্ন ব্যাংক', key: 'bank', ic: 'bookOpen' },
    { href: '/quiz/join', label: 'লাইভ কুইজ', key: 'quiz', ic: 'sparkles' },
  ];

  const renderNavLink = (item: (typeof navLinks)[number]) =>
    `<a href="${item.href}" class="nav-link${opts.activeNav === item.key ? ' active' : ''}">${icon(item.ic, 15)}<span>${item.label}</span></a>`;

  const authBlock = user
    ? `<div class="nav-user">
        <a href="/dashboard" class="nav-pill">${icon('layoutDashboard', 14)}<span>ড্যাশবোর্ড</span></a>
        ${user.is_admin ? `<a href="/admin/dashboard" class="nav-pill admin">${icon('shield', 14)}<span>Admin</span></a>` : ''}
        <a href="/logout" class="nav-link subtle-link">লগআউট</a>
      </div>`
    : `<div class="nav-user">
        <a href="/login" class="nav-link">লগইন</a>
        <a href="/register" class="btn btn-primary btn-sm">শুরু করুন</a>
      </div>`;

  const breadcrumbHtml =
    opts.breadcrumbs && opts.breadcrumbs.length > 0
      ? `<nav class="breadcrumb-bar" aria-label="Breadcrumb"><div class="container breadcrumb-inner">
          ${opts.breadcrumbs
            .map((b, i) => {
              const sep = i > 0 ? `<span class="bc-sep">${icon('chevronRight', 13)}</span>` : '';
              return b.href
                ? `${sep}<a href="${escapeHtml(b.href)}">${escapeHtml(b.label)}</a>`
                : `${sep}<span class="bc-current">${escapeHtml(b.label)}</span>`;
            })
            .join('')}
        </div></nav>`
      : '';

  return `<!DOCTYPE html>
<html lang="bn">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${escapeHtml(opts.title)} | Prosno.io</title>
  <meta name="description" content="${escapeHtml(opts.description || 'Prosno.io — বাংলাদেশের শিক্ষক ও কোচিং সেন্টারের জন্য আধুনিক MCQ, CQ, OMR ও লাইভ কুইজ প্ল্যাটফর্ম।')}">
  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Hind+Siliguri:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/css/app.css">
  ${opts.extraHead || ''}
</head>
<body>
  <a href="#main-content" class="skip-link">মূল কন্টেন্টে যান</a>

  <header class="site-header">
    <div class="container nav-wrap">
      <div class="nav-left">
        <button type="button" class="icon-btn mobile-only" id="mobileMenuOpen" aria-label="মেনু খুলুন">
          ${icon('menu', 20)}
        </button>
        <a href="/" class="brand">
          <span class="brand-badge">P</span>
          <span>Prosno.io</span>
        </a>
      </div>

      <nav class="main-nav desktop-only" aria-label="Main navigation">
        ${navLinks.map(renderNavLink).join('')}
      </nav>

      <div class="nav-right">
        <button type="button" class="cmd-trigger" id="cmdOpenBtn" title="দ্রুত নেভিগেশন (Ctrl+K)">
          ${icon('search', 14)}
          <span class="desktop-only">খুঁজুন</span>
          <kbd class="desktop-only">Ctrl K</kbd>
        </button>
        <div class="desktop-only">${authBlock}</div>
      </div>
    </div>
  </header>

  <!-- Mobile Slide-Over Navigation -->
  <div class="drawer-backdrop" id="mobileDrawerBackdrop"></div>
  <aside class="mobile-drawer" id="mobileDrawer" aria-hidden="true">
    <div class="drawer-head">
      <a href="/" class="brand"><span class="brand-badge">P</span><span>Prosno.io</span></a>
      <button type="button" class="icon-btn" id="mobileMenuClose" aria-label="মেনু বন্ধ করুন">${icon('x', 20)}</button>
    </div>
    <nav class="drawer-links">
      ${navLinks.map(renderNavLink).join('')}
      <div class="drawer-divider"></div>
      ${
        user
          ? `<a href="/dashboard" class="nav-link">${icon('layoutDashboard', 15)}<span>ড্যাশবোর্ড (${escapeHtml(user.display_name)})</span></a>
             <a href="/bank/profile" class="nav-link">${icon('sliders', 15)}<span>ব্র্যান্ডিং ও প্রোফাইল</span></a>
             ${user.is_admin ? `<a href="/admin/dashboard" class="nav-link">${icon('shield', 15)}<span>অ্যাডমিন প্যানেল</span></a>` : ''}
             <a href="/logout" class="nav-link">লগআউট</a>`
          : `<a href="/login" class="nav-link">লগইন</a>
             <a href="/register" class="btn btn-primary btn-block mt-1">বিনামূল্যে শুরু করুন</a>`
      }
    </nav>
  </aside>

  ${breadcrumbHtml}

  <main id="main-content" class="main-content">
    ${bodyHtml}
  </main>

  <footer class="site-footer">
    <div class="container footer-grid">
      <div class="footer-brand">
        <div class="brand"><span class="brand-badge">P</span><span>Prosno.io</span></div>
        <p>শিক্ষক ও কোচিং সেন্টারের জন্য ১-ক্লিকে বোর্ড-স্ট্যান্ডার্ড প্রশ্নপত্র, সমাধান, OMR শিট ও লাইভ কুইজ।</p>
      </div>
      <div class="footer-links">
        <a href="/generate">দ্রুত প্রশ্ন</a>
        <a href="/builder">পেপার বিল্ডার</a>
        <a href="/omr-builder">OMR ডিজাইনার</a>
        <a href="/bank/leaderboard">লিডারবোর্ড</a>
        <a href="/about">আমাদের সম্পর্কে</a>
        <a href="/contact">যোগাযোগ</a>
        <a href="/admin/login">অ্যাডমিন</a>
      </div>
    </div>
  </footer>

  <!-- Quick-Jump Command Palette -->
  <div class="cmd-overlay" id="cmdPalette" aria-hidden="true">
    <div class="cmd-modal" role="dialog" aria-label="দ্রুত নেভিগেশন">
      <div class="cmd-input-row">
        ${icon('search', 16)}
        <input type="text" id="cmdInput" placeholder="যেকোনো ফিচার খুঁজুন (যেমন: OMR, বিল্ডার, কুইজ)..." autocomplete="off">
        <button type="button" class="icon-btn" id="cmdCloseBtn" aria-label="বন্ধ করুন">${icon('x', 16)}</button>
      </div>
      <div class="cmd-list" id="cmdList"></div>
    </div>
  </div>

  <div id="toast-root" class="toast-root" aria-live="polite"></div>
  <script src="/js/ui.js"></script>
  ${opts.extraScripts || ''}
</body>
</html>`;
}
