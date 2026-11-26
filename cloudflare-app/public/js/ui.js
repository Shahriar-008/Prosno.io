(function () {
  // ── Global Toast System ─────────────────────────────────────────
  const toastRoot = document.getElementById('toast-root');
  function toast(message, type) {
    if (!toastRoot || !message) return;
    const item = document.createElement('div');
    item.className = 'toast-item toast-' + (type || 'info');
    item.setAttribute('role', 'status');
    item.textContent = message;
    toastRoot.appendChild(item);
    requestAnimationFrame(() => item.classList.add('show'));
    setTimeout(() => {
      item.classList.remove('show');
      setTimeout(() => item.remove(), 220);
    }, 3400);
  }
  window.ProsnoUI = { toast };

  // ── Mobile Slide-Over Drawer ────────────────────────────────────
  const drawer = document.getElementById('mobileDrawer');
  const backdrop = document.getElementById('mobileDrawerBackdrop');
  const openBtn = document.getElementById('mobileMenuOpen');
  const closeBtn = document.getElementById('mobileMenuClose');

  function setDrawer(open) {
    if (!drawer || !backdrop) return;
    drawer.classList.toggle('open', open);
    backdrop.classList.toggle('open', open);
    drawer.setAttribute('aria-hidden', open ? 'false' : 'true');
    document.body.style.overflow = open ? 'hidden' : '';
  }

  openBtn?.addEventListener('click', () => setDrawer(true));
  closeBtn?.addEventListener('click', () => setDrawer(false));
  backdrop?.addEventListener('click', () => setDrawer(false));

  // ── Quick-Jump Command Palette (Ctrl+K / Cmd+K) ─────────────────
  const cmdOverlay = document.getElementById('cmdPalette');
  const cmdInput = document.getElementById('cmdInput');
  const cmdList = document.getElementById('cmdList');
  const cmdOpenBtn = document.getElementById('cmdOpenBtn');
  const cmdCloseBtn = document.getElementById('cmdCloseBtn');

  const NAV_ITEMS = [
    { label: 'হোম পেজ', sub: 'Prosno.io মূল পেজ', href: '/', kw: 'home index main' },
    { label: 'দ্রুত প্রশ্নপত্র তৈরি', sub: 'অধ্যায় বেছে ১-ক্লিকে প্রশ্ন ও সমাধান', href: '/generate', kw: 'generate quick mcq' },
    { label: 'স্মার্ট পেপার বিল্ডার', sub: 'MCQ + সংক্ষিপ্ত + সৃজনশীল (CQ) সেকশন', href: '/builder', kw: 'builder cq sq section' },
    { label: 'OMR উত্তরপত্র ডিজাইনার', sub: '৪০/৬০/৮০/১০০ প্রিন্ট-রেডি OMR শিট', href: '/omr-builder', kw: 'omr sheet bubble' },
    { label: 'কমিউনিটি প্রশ্ন ব্যাংক', sub: 'শিক্ষকদের শেয়ার করা প্রশ্ন খুঁজুন', href: '/bank', kw: 'bank search community' },
    { label: 'নতুন প্রশ্ন জমা দিন', sub: 'প্রশ্ন ব্যাংকে প্রশ্ন যোগ করুন', href: '/bank/question/new', kw: 'new question bank' },
    { label: 'লাইভ কুইজে যোগ দিন', sub: '৪-ডিজিট কোডে অনলাইন পরীক্ষা', href: '/quiz/join', kw: 'quiz live join' },
    { label: 'শিক্ষক ড্যাশবোর্ড', sub: 'সেভ করা সেট, OMR ও কুইজ', href: '/dashboard', kw: 'dashboard saved sets' },
    { label: 'টিচার প্রোফাইল ও ব্র্যান্ডিং', sub: 'কোচিং লোগো ও ওয়াটারমার্ক সেটিংস', href: '/bank/profile', kw: 'profile branding logo' },
    { label: 'টিচার লিডারবোর্ড', sub: 'সেরা অবদানকারী শিক্ষক তালিকা', href: '/bank/leaderboard', kw: 'leaderboard rank' },
  ];

  let activeIndex = 0;
  let filteredItems = NAV_ITEMS.slice();

  function renderCmdItems() {
    if (!cmdList) return;
    if (!filteredItems.length) {
      cmdList.innerHTML = '<div class="cmd-empty">কোনো মিল পাওয়া যায়নি।</div>';
      return;
    }
    cmdList.innerHTML = filteredItems
      .map(
        (item, idx) => `<a href="${item.href}" class="cmd-item${idx === activeIndex ? ' active' : ''}" data-idx="${idx}">
          <div>
            <strong>${item.label}</strong>
            <span>${item.sub}</span>
          </div>
          <kbd>↵</kbd>
        </a>`
      )
      .join('');
  }

  function openCmd() {
    if (!cmdOverlay) return;
    setDrawer(false);
    cmdOverlay.classList.add('open');
    cmdOverlay.setAttribute('aria-hidden', 'false');
    filteredItems = NAV_ITEMS.slice();
    activeIndex = 0;
    if (cmdInput) {
      cmdInput.value = '';
      setTimeout(() => cmdInput.focus(), 40);
    }
    renderCmdItems();
  }

  function closeCmd() {
    if (!cmdOverlay) return;
    cmdOverlay.classList.remove('open');
    cmdOverlay.setAttribute('aria-hidden', 'true');
  }

  cmdOpenBtn?.addEventListener('click', openCmd);
  cmdCloseBtn?.addEventListener('click', closeCmd);
  cmdOverlay?.addEventListener('click', (e) => {
    if (e.target === cmdOverlay) closeCmd();
  });

  cmdInput?.addEventListener('input', () => {
    const q = cmdInput.value.trim().toLowerCase();
    filteredItems = !q
      ? NAV_ITEMS.slice()
      : NAV_ITEMS.filter(
          (i) =>
            i.label.toLowerCase().includes(q) ||
            i.sub.toLowerCase().includes(q) ||
            i.kw.includes(q)
        );
    activeIndex = 0;
    renderCmdItems();
  });

  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      if (cmdOverlay?.classList.contains('open')) closeCmd();
      else openCmd();
      return;
    }
    if (e.key === 'Escape') {
      setDrawer(false);
      closeCmd();
      return;
    }
    if (cmdOverlay?.classList.contains('open') && filteredItems.length) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        activeIndex = (activeIndex + 1) % filteredItems.length;
        renderCmdItems();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        activeIndex = (activeIndex - 1 + filteredItems.length) % filteredItems.length;
        renderCmdItems();
      } else if (e.key === 'Enter') {
        e.preventDefault();
        const target = filteredItems[activeIndex];
        if (target) location.href = target.href;
      }
    }
  });
})();
