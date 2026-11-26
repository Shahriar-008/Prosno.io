(function () {
  const bldClass = document.getElementById('bldClass');
  const bldSubject = document.getElementById('bldSubject');
  const bldBankResults = document.getElementById('bldBankResults');
  const bldSelected = document.getElementById('bldSelectedSections');
  const bldTotalMarks = document.getElementById('bldTotalMarks');
  const resultCard = document.getElementById('builderResultCard');

  const state = {
    mcq: [],
    sq: [],
    cq: [],
  };

  function renderSelected() {
    let marks = state.mcq.length + state.sq.length * 2 + state.cq.length * 10;
    bldTotalMarks.textContent = String(marks);
    const sections = [
      { key: 'mcq', label: 'MCQ প্রশ্ন', items: state.mcq },
      { key: 'sq', label: 'সংক্ষিপ্ত প্রশ্ন (SQ)', items: state.sq },
      { key: 'cq', label: 'সৃজনশীল প্রশ্ন (CQ)', items: state.cq },
    ];
    bldSelected.innerHTML = sections
      .map(
        (sec) => `<div class="mt-2"><strong>${sec.label} (${sec.items.length})</strong>` +
          sec.items
            .map(
              (item, idx) => `<div class="row-between mt-1" style="border-bottom:1px solid #e2e8f0;padding-bottom:4px;">
                <span class="small">${idx + 1}. ${item.label}</span>
                <button type="button" class="btn btn-sm btn-danger" onclick="window._bldRemove('${sec.key}',${idx})">×</button>
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
        return `<div class="card mt-1" style="padding:10px;">
          <p class="small" style="margin:0 0 6px 0;">${text.slice(0, 120)}</p>
          <button type="button" class="btn btn-sm btn-outline" data-add="${type}" data-id="${q.id}" data-src="${q.db_source || 'db'}" data-label="${encodeURIComponent(text.slice(0, 80))}">+ যোগ করুন</button>
        </div>`;
      })
      .join('') || '<p class="muted small">কোনো প্রশ্ন পাওয়া যায়নি</p>';

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
      });
    });
  }

  document.getElementById('bldFetchBank')?.addEventListener('click', fetchBank);

  document.getElementById('bldAddCustomMcq')?.addEventListener('click', () => {
    const qText = prompt('প্রশ্ন লিখুন:');
    if (!qText) return;
    const o1 = prompt('অপশন ক:', 'ক') || 'ক';
    const o2 = prompt('অপশন খ:', 'খ') || 'খ';
    const o3 = prompt('অপশন গ:', 'গ') || 'গ';
    const o4 = prompt('অপশন ঘ:', 'ঘ') || 'ঘ';
    const ans = prompt('সঠিক উত্তর:', o1) || o1;
    state.mcq.push({
      source: 'custom',
      question_text: qText,
      type: 'simple',
      answer_options: [o1, o2, o3, o4],
      correct_answer: ans,
      label: qText.slice(0, 80),
    });
    renderSelected();
  });

  document.getElementById('builderGenerateBtn')?.addEventListener('click', async () => {
    const sections = [];
    if (state.mcq.length) sections.push({ type: 'mcq', questions: state.mcq });
    if (state.sq.length) sections.push({ type: 'sq', questions: state.sq, answer_count: state.sq.length, marks_per_question: 2 });
    if (state.cq.length) sections.push({ type: 'cq', questions: state.cq, answer_count: state.cq.length });

    if (!sections.length) return alert('কমপক্ষে ১টি প্রশ্ন যোগ করুন।');
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
    if (!resp.ok) return alert(data.error || 'Failed (Login may be required)');
    resultCard.style.display = 'block';
    resultCard.innerHTML = `<h3>তৈরি সম্পন্ন!</h3><a href="${data.studio_url}" class="btn btn-primary mt-2">Print Studio-তে খুলুন</a>`;
  });

  renderSelected();
  fetchBank();
})();
