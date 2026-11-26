(function () {
  const bootEl = document.getElementById('omr-bootstrap');
  if (!bootEl) return;
  const boot = JSON.parse(bootEl.textContent || '{}');
  let config = JSON.parse(JSON.stringify(boot.defaultConfig));
  let currentTemplateId = null;

  const frame = document.getElementById('omrPreviewFrame');
  const variantEl = document.getElementById('omrVariant');
  const instWrap = document.getElementById('omrInstCountWrap');
  const genWrap = document.getElementById('omrGenCountWrap');
  const instCountEl = document.getElementById('omrInstCount');
  const genCountEl = document.getElementById('omrGenCount');
  const genColsEl = document.getElementById('omrGenCols');
  const themeEl = document.getElementById('omrTheme');
  const bubbleEl = document.getElementById('omrBubbleSize');
  const headerModeEl = document.getElementById('omrHeaderMode');
  const titleEl = document.getElementById('omrHeaderTitle');
  const subEl = document.getElementById('omrHeaderSubtitle');
  const instEl = document.getElementById('omrHeaderInstitution');
  const rollEl = document.getElementById('omrFieldRoll');
  const subjEl = document.getElementById('omrFieldSubj');
  const setEl = document.getElementById('omrFieldSet');
  const instrEl = document.getElementById('omrInstructions');

  let renderTimer = null;
  function syncFromControls() {
    config.sheet_variant = variantEl.value;
    if (config.sheet_variant === 'general') {
      instWrap.style.display = 'none';
      genWrap.style.display = '';
      config.answer_columns = Number(genColsEl.value) || 1;
      const maxQ = (boot.generalMaxByCol && boot.generalMaxByCol[config.answer_columns]) || 100;
      genCountEl.max = String(maxQ);
      config.question_count = Math.min(maxQ, Math.max(1, Number(genCountEl.value) || 50));
    } else {
      instWrap.style.display = '';
      genWrap.style.display = 'none';
      config.question_count = Number(instCountEl.value) || 100;
      config.answer_columns = 4;
    }
    config.theme_color = themeEl.value;
    config.bubble_size = bubbleEl.value;
    config.header_mode = headerModeEl.value;
    config.header = {
      title: titleEl.value,
      subtitle: subEl.value,
      institution: instEl.value,
    };
    config.fields = {
      roll: rollEl.checked,
      subject_code: subjEl.checked,
      set_code: setEl.checked,
    };
    if (!config.fields.roll && !config.fields.subject_code && !config.fields.set_code) {
      config.fields.roll = true;
      rollEl.checked = true;
    }
    config.instructions = instrEl.value.split(/\r?\n/).map((s) => s.trim()).filter(Boolean).slice(0, 6);

    document.getElementById('omrChipVariant').textContent = config.sheet_variant === 'general' ? 'General Normal' : 'Institutional';
    document.getElementById('omrChipCount').textContent = config.question_count + ' প্রশ্ন';
    document.getElementById('omrChipCols').textContent = config.answer_columns + ' কলাম';

    clearTimeout(renderTimer);
    renderTimer = setTimeout(renderPreview, 180);
  }

  async function renderPreview() {
    const resp = await fetch('/api/omr/render', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ config }),
    });
    if (resp.ok) {
      frame.srcdoc = await resp.text();
    }
  }

  [variantEl, instCountEl, genCountEl, genColsEl, themeEl, bubbleEl, headerModeEl, titleEl, subEl, instEl, rollEl, subjEl, setEl, instrEl].forEach((el) => {
    el?.addEventListener('input', syncFromControls);
    el?.addEventListener('change', syncFromControls);
  });

  document.getElementById('omrPrintBtn')?.addEventListener('click', () => {
    if (frame.contentWindow) {
      frame.contentWindow.focus();
      frame.contentWindow.print();
    }
  });

  if (boot.isAuthenticated) {
    const sel = document.getElementById('omrTplSelect');
    const nameEl = document.getElementById('omrTplName');
    const statusEl = document.getElementById('omrTplStatus');

    async function loadList() {
      const r = await fetch('/api/omr/templates');
      if (!r.ok) return;
      const d = await r.json();
      sel.innerHTML = '<option value="">টেমপ্লেট বাছাই করুন</option>' + (d.templates || []).map((t) => `<option value="${t.id}">${t.name} (${t.question_count})</option>`).join('');
    }
    loadList();

    document.getElementById('omrSaveBtn')?.addEventListener('click', async () => {
      const name = nameEl.value.trim() || 'OMR Sheet';
      const url = currentTemplateId ? `/api/omr/templates/${currentTemplateId}` : '/api/omr/templates';
      const method = currentTemplateId ? 'PUT' : 'POST';
      const r = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, config }),
      });
      const d = await r.json();
      if (r.ok) {
        currentTemplateId = d.template.id;
        statusEl.textContent = 'সেভ হয়েছে!';
        loadList();
      } else {
        statusEl.textContent = d.error || 'Error';
      }
    });

    document.getElementById('omrLoadBtn')?.addEventListener('click', async () => {
      const id = sel.value;
      if (!id) return;
      const r = await fetch(`/api/omr/templates/${id}`);
      const d = await r.json();
      if (!r.ok) return;
      currentTemplateId = d.template.id;
      nameEl.value = d.template.name;
      config = d.template.config_json;
      variantEl.value = config.sheet_variant;
      instCountEl.value = String(config.question_count);
      genCountEl.value = String(config.question_count);
      genColsEl.value = String(config.answer_columns);
      themeEl.value = config.theme_color;
      bubbleEl.value = config.bubble_size;
      headerModeEl.value = config.header_mode;
      titleEl.value = config.header.title || '';
      subEl.value = config.header.subtitle || '';
      instEl.value = config.header.institution || '';
      rollEl.checked = config.fields.roll;
      subjEl.checked = config.fields.subject_code;
      setEl.checked = config.fields.set_code;
      instrEl.value = (config.instructions || []).join('\n');
      syncFromControls();
    });

    document.getElementById('omrDeleteBtn')?.addEventListener('click', async () => {
      if (!currentTemplateId) return;
      await fetch(`/api/omr/templates/${currentTemplateId}/delete`, { method: 'POST' });
      currentTemplateId = null;
      nameEl.value = '';
      statusEl.textContent = 'ডিলিট হয়েছে';
      loadList();
    });
  }

  syncFromControls();
})();
