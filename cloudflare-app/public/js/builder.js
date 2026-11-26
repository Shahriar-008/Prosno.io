(function () {
  const bldClass = document.getElementById('bldClass');
  const bldSubject = document.getElementById('bldSubject');
  const bldBankResults = document.getElementById('bldBankResults');
  const bldSelected = document.getElementById('bldSelectedSections');
  const bldTotalMarks = document.getElementById('bldTotalMarks');
  const bldSummaryCounts = document.getElementById('bldSummaryCounts');
  const bldSummaryMarks = document.getElementById('bldSummaryMarks');
  const resultCard = document.getElementById('builderResultCard');
  const customBox = document.getElementById('bldCustomMcqForm');

  const state = {
    mcq: [],
    sq: [],
    cq: [],
  };

  function renderSelected() {
    const marks = state.mcq.length + state.sq.length * 2 + state.cq.length * 10;
    bldTotalMarks.textContent = String(marks);
    if (bldSummaryMarks) bldSummaryMarks.textContent = String(marks);
    if (bldSummaryCounts) {
      bldSummaryCounts.textContent = `MCQ: ${state.mcq.length} • SQ: ${state.sq.length} • CQ: ${state.cq.length}`;
    }

    const totalCount = state.mcq.length + state.sq.length + state.cq.length;
    if (totalCount === 0) {
      bldSelected.innerHTML =
        '<div class="empty-state"><strong>এখনো কোনো প্রশ্ন যুক্ত হয়নি</strong><p>ডানদিকের প্রশ্ন ব্যাংক প্যানেল থেকে বা উপরের "+ কাস্টম MCQ যোগ" বাটনে ক্লিক করে প্রশ্ন যোগ করুন।</p></div>';
      return;
    }

    const sections = [
      { key: 'mcq', label: 'MCQ প্রশ্ন', items: state.mcq },
      { key: 'sq', label: 'সংক্ষিপ্ত প্রশ্ন (SQ)', items: state.sq },
      { key: 'cq', label: 'সৃজনশীল প্রশ্ন (CQ)', items: state.cq },
    ];
    bldSelected.innerHTML = sections
      .filter((s) => s.items.length > 0)
      .map(
        (sec) => `<div class="mt-2"><strong>${sec.label} (${sec.items.length})</strong>` +
          sec.items
            .map(
              (item, idx) => `<div class="row-between mt-1" style="border-bottom:1px solid #e2e8f0;padding:6px 0;">
                <span class="small">${idx + 1}. ${item.label}</span>
                <button type="button" class="btn btn-sm btn-danger" onclick="window._bldRemove('${sec.key}',${idx})">সরান</button>
              </div>`
            )
            .join('') + '</div>'
      )
      .join('');
  }

  window._bldRemove = (key, idx) => {
    state[key].splice(idx, 1);
    renderSelected();
  };

  bldClass?.addEventListener('change', async () => {
    bldSubject.disabled = true;
    bldSubject.innerHTML = '<option value="">-- বিষয় --</option>';
    if (!bldClass.value) return;
    const r = await fetch('/api/subjects/' + bldClass.value);
    const subs = await r.json();
    bldSubject.innerHTML = '<option value="">-- বিষয় --</option>' + subs.map((s) => `<option value="${s.id}">${s.name_bn || s.name}</option>`).join('');
    bldSubject.disabled = false;
  });

  async function fetchBank() {
    const type = document.getElementById('bldType').value;
    const search = document.getElementById('bldSearch').value;
    bldBankResults.innerHTML = '<p class="muted small">খোঁজা হচ্ছে...</p>';
    const r = await fetch('/api/builder/questions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type,
        subject_id: Number(bldSubject.value) || null,
        search,
      }),
    });
    const d = await r.json();
    bldBankResults.innerHTML = (d.questions || [])
      .map((q) => {
        const text = q.question_text || q.stem || '';
        return `<div class="card mt-2" style="padding:12px;">
          <p class="small" style="margin:0 0 8px 0;">${text.slice(0, 120)}</p>
          <button type="button" class="btn btn-sm btn-outline" data-add="${type}" data-id="${q.id}" data-src="${q.db_source || 'db'}" data-label="${encodeURIComponent(text.slice(0, 80))}">+ যোগ করুন</button>
        </div>`;
      })
      .join('') || '<div class="empty-state mt-2"><p>কোনো প্রশ্ন পাওয়া যায়নি</p></div>';

    bldBankResults.querySelectorAll('[data-add]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const t = btn.dataset.add;
        state[t].push({
          source: 'db',
          id: Number(btn.dataset.id),
          db_source: btn.dataset.src,
          label: decodeURIComponent(btn.dataset.label),
        });
        renderSelected();
        window.ProsnoUI?.toast('প্রশ্ন যুক্ত হয়েছে', 'success');
      });
    });
  }

  document.getElementById('bldFetchBank')?.addEventListener('click', fetchBank);

  document.getElementById('bldToggleCustomForm')?.addEventListener('click', () => {
    if (!customBox) return;
    customBox.style.display = customBox.style.display === 'none' ? 'block' : 'none';
  });

  document.getElementById('bldAddCustomConfirm')?.addEventListener('click', () => {
    const qText = document.getElementById('bldCustText').value.trim();
    const o1 = document.getElementById('bldCustO1').value.trim();
    const o2 = document.getElementById('bldCustO2').value.trim();
    const o3 = document.getElementById('bldCustO3').value.trim();
    const o4 = document.getElementById('bldCustO4').value.trim();
    const ans = document.getElementById('bldCustAns').value.trim() || o1;
    if (!qText || !o1 || !o2 || !o3 || !o4) {
      window.ProsnoUI?.toast('প্রশ্ন এবং ৪টি অপশন পূরণ করুন', 'error');
      return;
    }
    state.mcq.push({
      source: 'custom',
      question_text: qText,
      type: 'simple',
      answer_options: [o1, o2, o3, o4],
      correct_answer: ans,
      label: qText.slice(0, 80),
    });
    ['bldCustText', 'bldCustO1', 'bldCustO2', 'bldCustO3', 'bldCustO4', 'bldCustAns'].forEach((id) => {
      document.getElementById(id).value = '';
    });
    if (customBox) customBox.style.display = 'none';
    renderSelected();
    window.ProsnoUI?.toast('কাস্টম MCQ যুক্ত হয়েছে', 'success');
  });

  document.getElementById('builderGenerateBtn')?.addEventListener('click', async () => {
    const sections = [];
    if (state.mcq.length) sections.push({ type: 'mcq', questions: state.mcq });
    if (state.sq.length) sections.push({ type: 'sq', questions: state.sq, answer_count: state.sq.length, marks_per_question: 2 });
    if (state.cq.length) sections.push({ type: 'cq', questions: state.cq, answer_count: state.cq.length });

    if (!sections.length) {
      window.ProsnoUI?.toast('কমপক্ষে ১টি প্রশ্ন যোগ করুন', 'error');
      return;
    }
    const resp = await fetch('/api/builder/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        paper_config: {
          title: document.getElementById('bldTitle').value || 'Question Paper',
          time_minutes: Number(document.getElementById('bldTime').value) || 60,
          class_id: Number(bldClass.value) || null,
          subject_id: Number(bldSubject.value) || null,
          omr_style: document.getElementById('bldOmr').checked,
        },
        sections,
      }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      window.ProsnoUI?.toast(data.error || 'তৈরি করতে লগইন প্রয়োজন', 'error');
      return;
    }
    resultCard.style.display = 'block';
    resultCard.innerHTML = `<h3>প্রশ্নপত্র তৈরি সম্পন্ন</h3><a href="${data.studio_url}" class="btn btn-primary mt-2">Print Studio-তে খুলুন</a>`;
    window.ProsnoUI?.toast('প্রশ্নপত্র তৈরি হয়েছে', 'success');
  });

  renderSelected();
  fetchBank();
})();
