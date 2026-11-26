(function () {
  const genClass = document.getElementById('genClass');
  const genSubject = document.getElementById('genSubject');
  const genChaptersBox = document.getElementById('genChaptersBox');
  const genAvailCount = document.getElementById('genAvailCount');
  const pickerBox = document.getElementById('questionPickerBox');
  const resultCard = document.getElementById('genResultCard');
  const errBanner = document.getElementById('genErrorBanner');

  const modeDbBtn = document.getElementById('modeDbBtn');
  const modeCustomBtn = document.getElementById('modeCustomBtn');
  const dbPanel = document.getElementById('dbModePanel');
  const customPanel = document.getElementById('customModePanel');
  const customList = document.getElementById('customQuestionsList');

  const step1 = document.getElementById('step1Pill');
  const step2 = document.getElementById('step2Pill');
  const step3 = document.getElementById('step3Pill');

  let selectedQuestionIds = new Set();

  function showError(msg) {
    if (errBanner) {
      errBanner.textContent = msg;
      errBanner.style.display = 'block';
    }
    window.ProsnoUI?.toast(msg, 'error');
  }
  function clearError() {
    if (errBanner) errBanner.style.display = 'none';
  }

  modeDbBtn?.addEventListener('click', () => {
    dbPanel.style.display = '';
    customPanel.style.display = 'none';
    modeDbBtn.classList.add('active');
    modeCustomBtn.classList.remove('active');
    clearError();
  });

  modeCustomBtn?.addEventListener('click', () => {
    dbPanel.style.display = 'none';
    customPanel.style.display = '';
    modeCustomBtn.classList.add('active');
    modeDbBtn.classList.remove('active');
    clearError();
    if (customList.children.length === 0) addCustomCard();
  });

  function getSelectedChapters() {
    return Array.from(genChaptersBox.querySelectorAll('input[type="checkbox"]:checked')).map((el) => Number(el.value));
  }

  genClass?.addEventListener('change', async () => {
    clearError();
    const classId = genClass.value;
    genSubject.disabled = true;
    genSubject.innerHTML = '<option value="">লোড হচ্ছে...</option>';
    genChaptersBox.textContent = 'বিষয় বাছাই করুন';
    if (!classId) {
      genSubject.innerHTML = '<option value="">-- আগে শ্রেণি বাছাই করুন --</option>';
      return;
    }
    const resp = await fetch('/api/subjects/' + classId);
    const subs = await resp.json();
    genSubject.innerHTML = '<option value="">-- বিষয় বাছাই করুন --</option>' + subs.map((s) => `<option value="${s.id}">${s.name_bn || s.name}</option>`).join('');
    genSubject.disabled = false;
  });

  genSubject?.addEventListener('change', async () => {
    clearError();
    const subjectId = genSubject.value;
    genChaptersBox.innerHTML = '<span class="muted">অধ্যায় লোড হচ্ছে...</span>';
    selectedQuestionIds.clear();
    if (!subjectId) {
      genChaptersBox.textContent = 'বিষয় বাছাই করুন';
      return;
    }
    const resp = await fetch('/api/chapters/' + subjectId);
    const chaps = await resp.json();
    if (!chaps.length) {
      genChaptersBox.textContent = 'কোনো অধ্যায় পাওয়া যায়নি';
      return;
    }
    genChaptersBox.innerHTML = chaps
      .map((ch) => `<label class="chapter-chip"><input type="checkbox" value="${ch.id}"> ${ch.name_bn || ch.name}</label>`)
      .join('');
    genChaptersBox.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
      cb.addEventListener('change', async () => {
        const ids = getSelectedChapters();
        if (ids.length > 5) {
          cb.checked = false;
          showError('সর্বোচ্চ ৫টি অধ্যায় নির্বাচন করা যাবে।');
          return;
        }
        clearError();
        if (ids.length > 0) step2?.classList.add('active');
        else step2?.classList.remove('active');
        const r = await fetch('/get-question-count', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ chapter_ids: ids }),
        });
        const d = await r.json();
        genAvailCount.textContent = (d.count || 0) + 'টি প্রশ্ন';
      });
    });
  });

  document.getElementById('btnPreviewQuestions')?.addEventListener('click', async () => {
    clearError();
    const ids = getSelectedChapters();
    if (!ids.length) return showError('কমপক্ষে ১টি অধ্যায় বাছাই করুন।');
    const r = await fetch('/get-questions-for-chapters', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chapter_ids: ids }),
    });
    const d = await r.json();
    pickerBox.style.display = 'block';
    pickerBox.innerHTML = (d.questions || [])
      .map(
        (q) => `<label class="chapter-chip" style="display:flex;margin-bottom:6px;"><input type="checkbox" class="pick-q" value="${q.id}" ${selectedQuestionIds.has(q.id) ? 'checked' : ''}> <span>#${q.id}: ${q.full_text}</span></label>`
      )
      .join('') || '<p class="muted">এই অধ্যায়গুলোতে এখনো কোনো প্রশ্ন যোগ করা হয়নি।</p>';
    pickerBox.querySelectorAll('.pick-q').forEach((el) => {
      el.addEventListener('change', () => {
        const qid = Number(el.value);
        if (el.checked) selectedQuestionIds.add(qid);
        else selectedQuestionIds.delete(qid);
      });
    });
  });

  function showResult(data) {
    step1?.classList.add('active');
    step2?.classList.add('active');
    step3?.classList.add('active');
    resultCard.style.display = 'block';
    resultCard.innerHTML = `
      <h3>প্রশ্নপত্র প্রস্তুত (${data.question_count}টি প্রশ্ন)</h3>
      <p class="muted small">এখন প্রিন্ট স্টুডিওতে ফন্ট, কলাম, লোগো বা ওয়াটারমার্ক পরিবর্তন করে PDF বা DOCX ডাউনলোড করতে পারবেন।</p>
      <div class="row-actions mt-2">
        <a href="${data.studio_url}" class="btn btn-primary">Live Print Studio খুলুন</a>
        <a href="${data.studio_url}?tab=answers" class="btn btn-outline">উত্তরমালা ও সমাধান</a>
      </div>`;
    window.ProsnoUI?.toast('প্রশ্নপত্র তৈরি সম্পন্ন হয়েছে', 'success');
    resultCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  document.getElementById('btnGenerateDb')?.addEventListener('click', async () => {
    clearError();
    const chapterIds = getSelectedChapters();
    if (!genClass.value || !genSubject.value || !chapterIds.length) {
      return showError('অনুগ্রহ করে শ্রেণি, বিষয় এবং কমপক্ষে ১টি অধ্যায় বাছাই করুন।');
    }
    const resp = await fetch('/generate-paper', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        class_id: Number(genClass.value),
        subject_id: Number(genSubject.value),
        chapter_ids: chapterIds,
        question_ids: Array.from(selectedQuestionIds),
        question_count: Number(document.getElementById('genCount').value) || 25,
        time_minutes: Number(document.getElementById('genTime').value) || 25,
        title: document.getElementById('genTitle').value || 'মডেল টেস্ট',
        randomize: document.getElementById('genRandomize').checked,
        omr_style: document.getElementById('genOmr').checked,
      }),
    });
    const data = await resp.json();
    if (!resp.ok) return showError(data.error || 'প্রশ্নপত্র তৈরি ব্যর্থ হয়েছে।');
    showResult(data);
  });

  function addCustomCard() {
    const idx = customList.children.length + 1;
    const div = document.createElement('div');
    div.className = 'inline-custom-box custom-q-item';
    div.innerHTML = `
      <label>প্রশ্ন ${idx} <input type="text" class="cq-text" required placeholder="প্রশ্ন লিখুন..."></label>
      <div class="grid-2 mt-2">
        <input type="text" class="cq-o1" placeholder="অপশন ক" required>
        <input type="text" class="cq-o2" placeholder="অপশন খ" required>
        <input type="text" class="cq-o3" placeholder="অপশন গ" required>
        <input type="text" class="cq-o4" placeholder="অপশন ঘ" required>
      </div>
      <label class="mt-2">সঠিক উত্তর <input type="text" class="cq-ans" placeholder="সঠিক অপশনের টেক্সট" required></label>`;
    customList.appendChild(div);
  }

  document.getElementById('btnAddCustomQ')?.addEventListener('click', addCustomCard);

  document.getElementById('btnGenerateCustom')?.addEventListener('click', async () => {
    clearError();
    const items = Array.from(customList.querySelectorAll('.custom-q-item')).map((card) => ({
      question_text: card.querySelector('.cq-text').value.trim(),
      type: 'simple',
      answer_options: [
        card.querySelector('.cq-o1').value.trim(),
        card.querySelector('.cq-o2').value.trim(),
        card.querySelector('.cq-o3').value.trim(),
        card.querySelector('.cq-o4').value.trim(),
      ],
      correct_answer: card.querySelector('.cq-ans').value.trim(),
    }));
    const resp = await fetch('/generate-custom-paper', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: document.getElementById('custTitle').value || 'কাস্টম পরীক্ষা',
        time_minutes: Number(document.getElementById('custTime').value) || 30,
        omr_style: document.getElementById('custOmr').checked,
        questions: items,
      }),
    });
    const data = await resp.json();
    if (!resp.ok) return showError(data.error || 'সব প্রশ্নের ঘর সঠিকভাবে পূরণ করুন।');
    showResult(data);
  });
})();
