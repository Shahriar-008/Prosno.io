(function () {
  const listEl = document.getElementById('bankList');
  const searchInput = document.getElementById('bankSearchInput');
  const typeFilter = document.getElementById('bankTypeFilter');
  const searchBtn = document.getElementById('bankSearchBtn');

  async function loadQuestions() {
    const q = encodeURIComponent(searchInput?.value || '');
    const t = encodeURIComponent(typeFilter?.value || '');
    listEl.innerHTML = '<div class="card"><p class="muted">প্রশ্ন খোঁজা হচ্ছে...</p></div>';
    const r = await fetch(`/api/v1/bank/search?q=${q}&type=${t}`);
    const d = await r.json();
    const items = d.items || [];
    if (!items.length) {
      listEl.innerHTML =
        '<div class="empty-state"><strong>কোনো পাবলিক প্রশ্ন পাওয়া যায়নি</strong><p>প্রথম প্রশ্নটি আপনিই যোগ করুন অথবা অন্য কীওয়ার্ড দিয়ে খুঁজুন।</p><a href="/bank/question/new" class="btn btn-primary btn-sm">+ নতুন প্রশ্ন যোগ করুন</a></div>';
      return;
    }
    listEl.innerHTML = items
      .map(
        (item) => `<div class="card mt-2">
          <div class="row-between">
            <span class="badge-pill">${item.question_type}</span>
            <span class="small muted">ব্যবহৃত: ${item.usage_count} • রেটিং: ${item.average_rating}</span>
          </div>
          <p class="mt-2"><strong>${item.question_text || item.stem || ''}</strong></p>
          <div class="row-actions">
            <button type="button" class="btn btn-sm btn-outline" onclick="saveBankQ(${item.id})">লাইব্রেরিতে সেভ</button>
          </div>
        </div>`
      )
      .join('');
  }

  window.saveBankQ = async (id) => {
    const r = await fetch(`/api/v1/bank/questions/${id}/save`, { method: 'POST' });
    if (r.ok) window.ProsnoUI?.toast('প্রশ্নটি আপনার লাইব্রেরিতে সেভ হয়েছে', 'success');
    else window.ProsnoUI?.toast('লাইব্রেরিতে সেভ করতে আগে লগইন করুন', 'error');
  };

  searchBtn?.addEventListener('click', loadQuestions);
  searchInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') loadQuestions();
  });
  loadQuestions();
})();
