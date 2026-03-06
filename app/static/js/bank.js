/**
 * bank.js — Teacher Question Bank Frontend Logic
 *
 * Modules: BankBrowser, BankQuestionForm, BankProfile,
 *          BankLibrary, BankNotifications, BankLeaderboard
 */

/* ── Shared Helpers ── */
const BankAPI = {
    base: '/api/v1/bank',

    _headers(userId) {
        const h = { 'Content-Type': 'application/json' };
        const csrf = document.querySelector('meta[name="csrf-token"]');
        if (csrf) h['X-CSRFToken'] = csrf.content;
        if (userId) h['X-Supabase-User-Id'] = userId;
        return h;
    },

    async get(path, userId) {
        const r = await fetch(this.base + path, { headers: this._headers(userId) });
        if (!r.ok) throw await r.json().catch(() => ({ error: r.statusText }));
        return r.json();
    },

    async post(path, body, userId) {
        const r = await fetch(this.base + path, {
            method: 'POST', headers: this._headers(userId),
            body: JSON.stringify(body)
        });
        if (!r.ok) throw await r.json().catch(() => ({ error: r.statusText }));
        return r.json();
    },

    async put(path, body, userId) {
        const r = await fetch(this.base + path, {
            method: 'PUT', headers: this._headers(userId),
            body: JSON.stringify(body)
        });
        if (!r.ok) throw await r.json().catch(() => ({ error: r.statusText }));
        return r.json();
    },

    async del(path, userId) {
        const r = await fetch(this.base + path, {
            method: 'DELETE', headers: this._headers(userId)
        });
        if (!r.ok) throw await r.json().catch(() => ({ error: r.statusText }));
        return r.json();
    }
};

function bankToast(msg, type) {
    const el = document.getElementById('bankToast');
    if (!el) return;
    el.textContent = msg;
    el.className = 'bank-toast ' + (type || '');
    requestAnimationFrame(() => el.classList.add('show'));
    setTimeout(() => el.classList.remove('show'), 3000);
}

function escapeHtml(str) {
    const d = document.createElement('div');
    d.textContent = str || '';
    return d.innerHTML;
}

function timeSince(dateStr) {
    const s = Math.floor((Date.now() - new Date(dateStr)) / 1000);
    if (s < 60) return 'just now';
    const m = Math.floor(s / 60);
    if (m < 60) return m + 'm ago';
    const h = Math.floor(m / 60);
    if (h < 24) return h + 'h ago';
    const d = Math.floor(h / 24);
    if (d < 30) return d + 'd ago';
    return new Date(dateStr).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

function renderStars(avg, count) {
    let html = '';
    const full = Math.round(avg);
    for (let i = 1; i <= 5; i++) {
        html += `<i class="bi bi-star${i <= full ? '-fill' : ''} star${i <= full ? ' filled' : ''}"></i>`;
    }
    if (count > 0) html += ` <span style="font-size:.75rem;color:var(--bank-slate-600);">(${count})</span>`;
    return html;
}

function diffBadge(d) {
    return `<span class="bank-diff bank-diff-${escapeHtml(d)}">${escapeHtml(d)}</span>`;
}

function visBadge(v) {
    return `<span class="bank-vis bank-vis-${escapeHtml(v)}"><i class="bi bi-${v === 'public' ? 'globe' : v === 'pending' ? 'hourglass-split' : v === 'rejected' ? 'x-circle' : 'lock'}"></i> ${escapeHtml(v)}</span>`;
}

function renderPagination(container, page, pages, onPage) {
    container.innerHTML = '';
    if (pages <= 1) { container.style.display = 'none'; return; }
    container.style.display = 'flex';
    for (let i = 1; i <= pages; i++) {
        if (pages > 7 && i > 3 && i < pages - 2 && Math.abs(i - page) > 1) {
            if (container.lastElementChild && container.lastElementChild.textContent !== '…') {
                const dot = document.createElement('span');
                dot.className = 'bank-page-btn';
                dot.textContent = '…';
                dot.style.pointerEvents = 'none';
                container.appendChild(dot);
            }
            continue;
        }
        const btn = document.createElement('button');
        btn.className = 'bank-page-btn' + (i === page ? ' active' : '');
        btn.textContent = i;
        btn.addEventListener('click', () => onPage(i));
        container.appendChild(btn);
    }
}


/* ══════════════════════════════════════════
   BankBrowser — Browse Classes → Questions
   ══════════════════════════════════════════ */
const BankBrowser = {
    cfg: {},
    level: 'classes',
    breadcrumbs: [],
    currentChapterId: null,
    currentType: 'all',
    currentSort: 'newest',
    currentDiff: '',
    currentPage: 1,

    init(cfg) {
        this.cfg = cfg;
        BankAPI.base = cfg.apiBase || '/api/v1/bank';
        this.loadClasses();
        this._bindFilters();
    },

    _bindFilters() {
        document.querySelectorAll('#bankTypeTabs .bank-type-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('#bankTypeTabs .bank-type-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                this.currentType = tab.dataset.type;
                this.currentPage = 1;
                this.loadQuestions();
            });
        });
        const sortSel = document.getElementById('bankSortSelect');
        if (sortSel) sortSel.addEventListener('change', () => {
            this.currentSort = sortSel.value;
            this.currentPage = 1;
            this.loadQuestions();
        });
        const diffSel = document.getElementById('bankDiffFilter');
        if (diffSel) diffSel.addEventListener('change', () => {
            this.currentDiff = diffSel.value;
            this.currentPage = 1;
            this.loadQuestions();
        });
        const searchInput = document.getElementById('bankSearchInput');
        if (searchInput) {
            let timeout;
            searchInput.addEventListener('input', () => {
                clearTimeout(timeout);
                timeout = setTimeout(() => { this.currentPage = 1; this.loadQuestions(); }, 400);
            });
        }
    },

    _showGrid() {
        document.getElementById('bankGrid').style.display = '';
        document.getElementById('bankQuestionList').style.display = 'none';
        document.getElementById('bankFilters').style.display = 'none';
        document.getElementById('bankSearchWrap').style.display = 'none';
        document.getElementById('bankPagination').style.display = 'none';
    },

    _showQuestions() {
        document.getElementById('bankGrid').style.display = 'none';
        document.getElementById('bankQuestionList').style.display = '';
        document.getElementById('bankFilters').style.display = '';
        document.getElementById('bankSearchWrap').style.display = '';
    },

    _updateBreadcrumb() {
        const bc = document.getElementById('bankBreadcrumb');
        let html = `<a href="javascript:void(0)" onclick="BankBrowser.loadClasses()"><i class="bi bi-collection"></i> Question Bank</a>`;
        this.breadcrumbs.forEach((item, i) => {
            html += `<span class="sep"><i class="bi bi-chevron-right"></i></span>`;
            if (i < this.breadcrumbs.length - 1) {
                html += `<a href="javascript:void(0)" onclick="BankBrowser.navigateTo(${i})">${escapeHtml(item.name_bn || item.name)}</a>`;
            } else {
                html += `<span class="current">${escapeHtml(item.name_bn || item.name)}</span>`;
            }
        });
        bc.innerHTML = html;
    },

    navigateTo(idx) {
        const item = this.breadcrumbs[idx];
        this.breadcrumbs = this.breadcrumbs.slice(0, idx);
        if (item.type === 'class') {
            this.loadSubjects(item.id, item);
        } else if (item.type === 'subject') {
            this.loadChapters(item.id, item);
        }
    },

    _renderGrid(items, onClick) {
        const grid = document.getElementById('bankGrid');
        grid.innerHTML = '';
        if (!items.length) {
            grid.innerHTML = `<div class="bank-empty" style="grid-column:1/-1;">
                <i class="bi bi-inbox"></i><h3>Nothing here yet</h3>
                <p>No items found at this level.</p></div>`;
            return;
        }
        items.forEach(item => {
            const card = document.createElement('div');
            card.className = 'bank-card';
            card.innerHTML = `
                <div class="bank-card-name">${escapeHtml(item.name)}</div>
                ${item.name_bn ? `<div class="bank-card-name-bn">${escapeHtml(item.name_bn)}</div>` : ''}
                <div class="bank-card-count"><i class="bi bi-chat-square-text"></i> ${item.question_count || 0} questions</div>
            `;
            card.addEventListener('click', () => onClick(item));
            grid.appendChild(card);
        });
    },

    async loadClasses() {
        this.level = 'classes';
        this.breadcrumbs = [];
        this._showGrid();
        this._updateBreadcrumb();
        document.getElementById('bankTitle').textContent = 'Question Bank';
        document.getElementById('bankSubtitle').textContent = 'Browse community-contributed questions by class, subject, and chapter';
        const grid = document.getElementById('bankGrid');
        grid.innerHTML = Array(6).fill('<div class="bank-skeleton bank-skeleton-card"></div>').join('');
        try {
            const data = await BankAPI.get('/browse/classes', this.cfg.userId);
            this._renderGrid(data, (cls) => this.loadSubjects(cls.id, cls));
        } catch (e) {
            grid.innerHTML = `<div class="bank-empty" style="grid-column:1/-1;">
                <i class="bi bi-exclamation-triangle"></i><h3>Could not load classes</h3></div>`;
        }
    },

    async loadSubjects(classId, classItem) {
        this.level = 'subjects';
        this.breadcrumbs = [{ ...classItem, type: 'class' }];
        this._showGrid();
        this._updateBreadcrumb();
        document.getElementById('bankTitle').textContent = classItem.name_bn || classItem.name;
        document.getElementById('bankSubtitle').textContent = 'Select a subject';
        const grid = document.getElementById('bankGrid');
        grid.innerHTML = Array(4).fill('<div class="bank-skeleton bank-skeleton-card"></div>').join('');
        try {
            const data = await BankAPI.get(`/browse/subjects/${classId}`, this.cfg.userId);
            this._renderGrid(data, (subj) => this.loadChapters(subj.id, subj));
        } catch (e) {
            grid.innerHTML = `<div class="bank-empty" style="grid-column:1/-1;">
                <i class="bi bi-exclamation-triangle"></i><h3>Could not load subjects</h3></div>`;
        }
    },

    async loadChapters(subjectId, subjectItem) {
        this.level = 'chapters';
        if (this.breadcrumbs.length === 1) {
            this.breadcrumbs.push({ ...subjectItem, type: 'subject' });
        }
        this._showGrid();
        this._updateBreadcrumb();
        document.getElementById('bankTitle').textContent = subjectItem.name_bn || subjectItem.name;
        document.getElementById('bankSubtitle').textContent = 'Select a chapter';
        const grid = document.getElementById('bankGrid');
        grid.innerHTML = Array(5).fill('<div class="bank-skeleton bank-skeleton-card"></div>').join('');
        try {
            const data = await BankAPI.get(`/browse/chapters/${subjectId}`, this.cfg.userId);
            this._renderGrid(data, (ch) => this.openChapter(ch));
        } catch (e) {
            grid.innerHTML = `<div class="bank-empty" style="grid-column:1/-1;">
                <i class="bi bi-exclamation-triangle"></i><h3>Could not load chapters</h3></div>`;
        }
    },

    openChapter(chapterItem) {
        this.level = 'questions';
        this.currentChapterId = chapterItem.id;
        this.currentType = 'all';
        this.currentPage = 1;
        if (this.breadcrumbs.length === 2) {
            this.breadcrumbs.push({ ...chapterItem, type: 'chapter' });
        }
        this._showQuestions();
        this._updateBreadcrumb();
        document.getElementById('bankTitle').textContent = chapterItem.name_bn || chapterItem.name;
        document.getElementById('bankSubtitle').textContent = 'Questions in this chapter';
        // Reset type tabs
        document.querySelectorAll('#bankTypeTabs .bank-type-tab').forEach(t => {
            t.classList.toggle('active', t.dataset.type === 'all');
        });
        this.loadQuestions();
    },

    async loadQuestions() {
        const list = document.getElementById('bankQuestionList');
        list.innerHTML = Array(3).fill('<div class="bank-skeleton bank-skeleton-row"></div>').join('');
        const searchVal = (document.getElementById('bankSearchInput') || {}).value || '';

        let path;
        if (searchVal.trim()) {
            const params = new URLSearchParams({
                q: searchVal.trim(),
                chapter_id: this.currentChapterId,
                sort: this.currentSort,
                page: this.currentPage,
                per_page: 15
            });
            if (this.currentType !== 'all') params.set('question_type', this.currentType);
            if (this.currentDiff) params.set('difficulty', this.currentDiff);
            path = '/search?' + params.toString();
        } else {
            let qs = `?sort=${this.currentSort}&page=${this.currentPage}&per_page=15`;
            if (this.currentDiff) qs += `&difficulty=${this.currentDiff}`;
            path = `/browse/chapters/${this.currentChapterId}/questions` + qs;
        }

        try {
            const data = await BankAPI.get(path, this.cfg.userId);
            this._renderQuestionData(data, searchVal.trim());
        } catch (e) {
            list.innerHTML = `<div class="bank-empty"><i class="bi bi-exclamation-triangle"></i><h3>Could not load questions</h3></div>`;
        }
    },

    _renderQuestionData(data, isSearch) {
        const list = document.getElementById('bankQuestionList');
        list.innerHTML = '';

        let questions, total, pages;
        if (isSearch) {
            questions = data.items || [];
            total = data.total || 0;
            pages = data.pages || 1;
        } else {
            // Grouped response from browse
            const counts = data.counts || {};
            document.getElementById('countAll').textContent = data.total || 0;
            document.getElementById('countMCQ').textContent = counts.MCQ || 0;
            document.getElementById('countSQ').textContent = counts.SQ || 0;
            document.getElementById('countCQ').textContent = counts.CQ || 0;

            if (this.currentType === 'all') {
                questions = [].concat(data.grouped?.MCQ || [], data.grouped?.SQ || [], data.grouped?.CQ || []);
            } else {
                questions = data.grouped?.[this.currentType] || [];
            }
            total = data.total || 0;
            pages = data.pages || 1;
        }

        if (!questions.length) {
            list.innerHTML = `<div class="bank-empty"><i class="bi bi-chat-square"></i><h3>No questions found</h3>
                <p>Try changing the filters or be the first to contribute!</p></div>`;
            document.getElementById('bankPagination').style.display = 'none';
            return;
        }

        questions.forEach(q => list.appendChild(this._renderQuestionCard(q)));
        renderPagination(
            document.getElementById('bankPagination'),
            this.currentPage, pages,
            (p) => { this.currentPage = p; this.loadQuestions(); }
        );
    },

    _renderQuestionCard(q) {
        const div = document.createElement('div');
        div.className = 'bank-question-item';
        const avg = q.rating_count ? (q.rating_total / q.rating_count).toFixed(1) : 0;

        let optionsHtml = '';
        if (q.question_type === 'MCQ' && q.answer_options) {
            const labels = ['ক', 'খ', 'গ', 'ঘ'];
            optionsHtml = '<div class="bank-mcq-options">' +
                (q.answer_options || []).map((opt, i) =>
                    `<div class="bank-mcq-option${opt === q.correct_answer ? ' correct' : ''}">
                        <span class="opt-label">${labels[i] || ''}</span> ${escapeHtml(opt)}
                    </div>`
                ).join('') + '</div>';
        }

        let actionsHtml = '';
        if (this.cfg.isLoggedIn) {
            actionsHtml = `<div class="bank-question-actions">
                <button class="bank-btn bank-btn-outline" onclick="BankBrowser.saveQuestion(${q.id})" title="Save to library">
                    <i class="bi bi-bookmark"></i> Save
                </button>
                <button class="bank-btn bank-btn-ghost" onclick="BankBrowser.openRateModal(${q.id})" title="Rate this question">
                    <i class="bi bi-star"></i> Rate
                </button>
                <button class="bank-btn bank-btn-ghost" onclick="BankBrowser.copyQuestion(${q.id})" title="Copy to my questions">
                    <i class="bi bi-copy"></i> Copy
                </button>
            </div>`;
        }

        div.innerHTML = `
            <div class="d-flex justify-content-between align-items-start gap-2 flex-wrap">
                <span class="bank-diff bank-diff-${escapeHtml(q.difficulty || 'medium')}">${escapeHtml(q.difficulty || 'medium')}</span>
                <span style="font-size:.75rem;color:var(--bank-slate-600);">${escapeHtml(q.question_type)}</span>
            </div>
            <div class="bank-question-text">${escapeHtml(q.question_text)}</div>
            ${optionsHtml}
            <div class="bank-question-meta">
                <span class="meta-item"><i class="bi bi-bar-chart"></i> ${q.usage_count || 0} uses</span>
                <span class="meta-item"><i class="bi bi-star-fill"></i> ${avg > 0 ? avg : '—'}</span>
                <span class="meta-item"><i class="bi bi-hash"></i> ${q.marks || 1} mark${(q.marks || 1) > 1 ? 's' : ''}</span>
            </div>
            ${actionsHtml}
        `;
        return div;
    },

    /* ── Actions (save / rate / copy) ── */
    _ratingTarget: null,
    _ratingValue: 0,

    async saveQuestion(id) {
        try {
            await BankAPI.post(`/questions/${id}/save`, {}, this.cfg.userId);
            bankToast('Saved to library!', 'success');
        } catch (e) {
            bankToast(e.error || 'Could not save', 'error');
        }
    },

    async copyQuestion(id) {
        try {
            await BankAPI.post(`/questions/${id}/copy`, {}, this.cfg.userId);
            bankToast('Copied to your questions!', 'success');
        } catch (e) {
            bankToast(e.error || 'Could not copy', 'error');
        }
    },

    openRateModal(id) {
        this._ratingTarget = id;
        this._ratingValue = 0;
        document.querySelectorAll('#rateStars .star').forEach(s => {
            s.className = 'bi bi-star star';
        });
        document.getElementById('rateSubmitBtn').disabled = true;
        document.getElementById('rateModal').classList.add('show');

        document.querySelectorAll('#rateStars .star').forEach(s => {
            s.onclick = () => {
                this._ratingValue = parseInt(s.dataset.val);
                document.querySelectorAll('#rateStars .star').forEach((st, i) => {
                    st.className = `bi bi-star${i < this._ratingValue ? '-fill' : ''} star${i < this._ratingValue ? ' filled' : ''}`;
                });
                document.getElementById('rateSubmitBtn').disabled = false;
            };
        });

        document.getElementById('rateSubmitBtn').onclick = async () => {
            try {
                await BankAPI.post(`/questions/${this._ratingTarget}/rate`, { rating: this._ratingValue }, this.cfg.userId);
                bankToast('Rating submitted!', 'success');
                closeRateModal();
            } catch (e) {
                bankToast(e.error || 'Could not rate', 'error');
            }
        };
    }
};

function closeRateModal() {
    document.getElementById('rateModal').classList.remove('show');
}


/* ══════════════════════════════════════════
   BankQuestionForm — Create Question
   ══════════════════════════════════════════ */
const BankQuestionForm = {
    cfg: {},
    selectedType: 'MCQ',
    correctIdx: -1,

    init(cfg) {
        this.cfg = cfg;
        BankAPI.base = cfg.apiBase || '/api/v1/bank';
        this._loadClasses();
        this._bindTypeTabs();
        this._bindCorrectAnswer();
        this._bindSubmit();
        this._bindCascade();
    },

    async _loadClasses() {
        try {
            const data = await BankAPI.get('/browse/classes', this.cfg.userId);
            const sel = document.getElementById('qfClass');
            data.forEach(c => {
                const opt = document.createElement('option');
                opt.value = c.id;
                opt.textContent = c.name_bn || c.name;
                sel.appendChild(opt);
            });
        } catch (e) { /* silent */ }
    },

    _bindCascade() {
        document.getElementById('qfClass').addEventListener('change', async (e) => {
            const subjSel = document.getElementById('qfSubject');
            const chapSel = document.getElementById('qfChapter');
            subjSel.innerHTML = '<option value="">Select subject...</option>';
            chapSel.innerHTML = '<option value="">Select chapter...</option>';
            chapSel.disabled = true;
            if (!e.target.value) { subjSel.disabled = true; return; }
            subjSel.disabled = false;
            try {
                const data = await BankAPI.get(`/browse/subjects/${e.target.value}`, this.cfg.userId);
                data.forEach(s => {
                    const opt = document.createElement('option');
                    opt.value = s.id;
                    opt.textContent = s.name_bn || s.name;
                    subjSel.appendChild(opt);
                });
            } catch (e) { /* silent */ }
        });

        document.getElementById('qfSubject').addEventListener('change', async (e) => {
            const chapSel = document.getElementById('qfChapter');
            chapSel.innerHTML = '<option value="">Select chapter...</option>';
            if (!e.target.value) { chapSel.disabled = true; return; }
            chapSel.disabled = false;
            try {
                const data = await BankAPI.get(`/browse/chapters/${e.target.value}`, this.cfg.userId);
                data.forEach(c => {
                    const opt = document.createElement('option');
                    opt.value = c.id;
                    opt.textContent = c.name_bn || c.name;
                    chapSel.appendChild(opt);
                });
            } catch (e) { /* silent */ }
        });
    },

    _bindTypeTabs() {
        document.querySelectorAll('#qfTypeTabs .bank-type-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('#qfTypeTabs .bank-type-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                this.selectedType = tab.dataset.type;
                document.getElementById('qfMcqFields').style.display = this.selectedType === 'MCQ' ? '' : 'none';
                document.getElementById('qfSqFields').style.display = this.selectedType === 'SQ' ? '' : 'none';
                document.getElementById('qfCqFields').style.display = this.selectedType === 'CQ' ? '' : 'none';
            });
        });
    },

    _bindCorrectAnswer() {
        document.querySelectorAll('.opt-letter').forEach(el => {
            el.addEventListener('click', () => {
                const idx = parseInt(el.dataset.idx);
                this.correctIdx = idx;
                document.querySelectorAll('.opt-letter').forEach(l => l.classList.remove('selected'));
                el.classList.add('selected');
            });
        });
    },

    _bindSubmit() {
        document.getElementById('bankQuestionForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('qfSubmitBtn');
            btn.disabled = true;
            btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Saving...';

            const body = {
                question_type: this.selectedType,
                question_text: document.getElementById('qfText').value.trim(),
                explanation: document.getElementById('qfExplanation').value.trim(),
                class_id: parseInt(document.getElementById('qfClass').value),
                subject_id: parseInt(document.getElementById('qfSubject').value),
                chapter_id: parseInt(document.getElementById('qfChapter').value),
                difficulty: document.getElementById('qfDifficulty').value,
                marks: parseInt(document.getElementById('qfMarks').value) || 1,
                topic: document.getElementById('qfTopic').value.trim(),
                board: document.getElementById('qfBoard').value.trim(),
                year: parseInt(document.getElementById('qfYear').value) || null,
            };

            if (this.selectedType === 'MCQ') {
                const opts = [];
                document.querySelectorAll('.mcq-option').forEach(inp => opts.push(inp.value.trim()));
                body.answer_options = opts;
                if (this.correctIdx >= 0 && this.correctIdx < opts.length) {
                    body.correct_answer = opts[this.correctIdx];
                }
            } else if (this.selectedType === 'SQ') {
                body.answer = document.getElementById('qfAnswer').value.trim();
            } else if (this.selectedType === 'CQ') {
                body.stem = document.getElementById('qfStem').value.trim();
                body.part_ka = document.getElementById('qfPartKa').value.trim();
                body.part_kha = document.getElementById('qfPartKha').value.trim();
                body.part_ga = document.getElementById('qfPartGa').value.trim();
                body.part_gha = document.getElementById('qfPartGha').value.trim();
                body.marks_ka = parseInt(document.getElementById('qfMarksKa').value) || null;
                body.marks_kha = parseInt(document.getElementById('qfMarksKha').value) || null;
                body.marks_ga = parseInt(document.getElementById('qfMarksGa').value) || null;
                body.marks_gha = parseInt(document.getElementById('qfMarksGha').value) || null;
            }

            try {
                await BankAPI.post('/questions', body, this.cfg.userId);
                bankToast('Question saved! It\'s in your private questions.', 'success');
                setTimeout(() => { window.location.href = '/bank/profile'; }, 1200);
            } catch (err) {
                bankToast(err.error || 'Could not save question', 'error');
                btn.disabled = false;
                btn.innerHTML = '<i class="bi bi-check-lg"></i> Save Question';
            }
        });
    }
};


/* ══════════════════════════════════════════
   BankProfile — Own / Public profile + My Questions
   ══════════════════════════════════════════ */
const BankProfile = {
    cfg: {},
    currentType: '',
    currentVis: '',
    currentPage: 1,

    init(cfg) {
        this.cfg = cfg;
        BankAPI.base = cfg.apiBase || '/api/v1/bank';
        this._loadProfile();
        if (cfg.isOwnProfile) {
            this._loadOwnQuestions();
            this._bindFilters();
        }
    },

    async _loadProfile() {
        try {
            let data;
            if (this.cfg.isOwnProfile) {
                data = await BankAPI.get('/profile', this.cfg.userId);
            } else {
                data = await BankAPI.get(`/teachers/${this.cfg.userId}/profile`, this.cfg.viewerUserId);
            }
            this._renderProfile(data);
        } catch (e) {
            document.getElementById('profileName').textContent = 'Could not load profile';
        }
    },

    _renderProfile(p) {
        const name = p.display_name || 'Teacher';
        document.getElementById('profileAvatar').textContent = name[0].toUpperCase();
        document.getElementById('profileName').textContent = name;
        const rankEl = document.getElementById('profileRank');
        if (rankEl) rankEl.innerHTML = `<i class="bi bi-award"></i> ${escapeHtml(p.contributor_rank || 'Newcomer')}`;

        const trustEl = document.getElementById('profileTrustBadge');
        if (trustEl && p.is_trusted) {
            trustEl.innerHTML = `<span class="bank-badge bank-badge-gold"><i class="bi bi-patch-check-fill"></i> Trusted</span>`;
        }

        const sc = document.getElementById('statCreated');
        const sp = document.getElementById('statPublished');
        const sr = document.getElementById('statReputation');
        const su = document.getElementById('statUsed');
        if (sc) sc.textContent = p.questions_created || 0;
        if (sp) sp.textContent = p.questions_published || 0;
        if (sr) sr.textContent = Math.round(p.reputation_score || 0);
        if (su) su.textContent = p.questions_used || 0;

        // Badges
        const badgesEl = document.getElementById('profileBadges');
        if (badgesEl && p.badges && p.badges.length) {
            badgesEl.innerHTML = p.badges.map(b =>
                `<span class="bank-badge bank-badge-${escapeHtml(b.icon || 'silver')}">
                    <i class="bi bi-award-fill"></i> ${escapeHtml(b.name || b.badge_name)}
                </span>`
            ).join('');
        }

        // For public profile breadcrumb
        const bcName = document.getElementById('teacherBreadcrumbName');
        if (bcName) bcName.textContent = name;
        const titleEl = document.getElementById('teacherTitle');
        if (titleEl) titleEl.textContent = `${name}'s Questions`;
    },

    _bindFilters() {
        document.querySelectorAll('#profileTypeTabs .bank-type-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('#profileTypeTabs .bank-type-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                this.currentType = tab.dataset.type;
                this.currentPage = 1;
                this._loadOwnQuestions();
            });
        });
        document.querySelectorAll('#profileVisTabs .bank-filter-pill').forEach(pill => {
            pill.addEventListener('click', () => {
                document.querySelectorAll('#profileVisTabs .bank-filter-pill').forEach(p => p.classList.remove('active'));
                pill.classList.add('active');
                this.currentVis = pill.dataset.vis;
                this.currentPage = 1;
                this._loadOwnQuestions();
            });
        });
    },

    async _loadOwnQuestions() {
        const list = document.getElementById('profileQuestionList');
        list.innerHTML = Array(3).fill('<div class="bank-skeleton bank-skeleton-row"></div>').join('');
        const params = new URLSearchParams({ page: this.currentPage, per_page: 10 });
        if (this.currentType) params.set('question_type', this.currentType);
        if (this.currentVis) params.set('visibility', this.currentVis);

        try {
            const data = await BankAPI.get('/questions?' + params.toString(), this.cfg.userId);
            list.innerHTML = '';
            if (!(data.items || []).length) {
                list.innerHTML = `<div class="bank-empty"><i class="bi bi-journal-plus"></i><h3>No questions yet</h3>
                    <p>Start contributing to the community bank!</p>
                    <a href="/bank/question/new" class="bank-btn bank-btn-primary bank-btn-lg mt-2">
                        <i class="bi bi-plus-lg"></i> Add Question</a></div>`;
                return;
            }
            data.items.forEach(q => {
                const div = document.createElement('div');
                div.className = 'bank-question-item';
                div.innerHTML = `
                    <div class="d-flex justify-content-between align-items-start gap-2 flex-wrap">
                        <div class="d-flex gap-2 align-items-center">
                            ${visBadge(q.visibility || 'private')}
                            ${diffBadge(q.difficulty || 'medium')}
                        </div>
                        <span style="font-size:.75rem;color:var(--bank-slate-600);">${escapeHtml(q.question_type)} · ${timeSince(q.created_at)}</span>
                    </div>
                    <div class="bank-question-text">${escapeHtml(q.question_text)}</div>
                    <div class="bank-question-meta">
                        <span class="meta-item"><i class="bi bi-bar-chart"></i> ${q.usage_count || 0} uses</span>
                        <span class="meta-item"><i class="bi bi-hash"></i> ${q.marks || 1} mark${(q.marks || 1) > 1 ? 's' : ''}</span>
                    </div>`;
                list.appendChild(div);
            });
            renderPagination(
                document.getElementById('profilePagination'),
                this.currentPage, data.pages || 1,
                (p) => { this.currentPage = p; this._loadOwnQuestions(); }
            );
        } catch (e) {
            list.innerHTML = `<div class="bank-empty"><i class="bi bi-exclamation-triangle"></i><h3>Could not load questions</h3></div>`;
        }
    }
};


/* ══════════════════════════════════════════
   BankLibrary — Saved Questions
   ══════════════════════════════════════════ */
const BankLibrary = {
    cfg: {},
    currentPage: 1,

    init(cfg) {
        this.cfg = cfg;
        BankAPI.base = cfg.apiBase || '/api/v1/bank';
        this._load();
        const searchInput = document.getElementById('librarySearch');
        if (searchInput) {
            let timeout;
            searchInput.addEventListener('input', () => {
                clearTimeout(timeout);
                timeout = setTimeout(() => { this.currentPage = 1; this._load(); }, 400);
            });
        }
    },

    async _load() {
        const list = document.getElementById('libraryList');
        list.innerHTML = Array(3).fill('<div class="bank-skeleton bank-skeleton-row"></div>').join('');
        document.getElementById('libraryEmpty').style.display = 'none';
        const params = new URLSearchParams({ page: this.currentPage, per_page: 15 });
        try {
            const data = await BankAPI.get('/library?' + params.toString(), this.cfg.userId);
            const items = data.items || [];
            document.getElementById('libraryCount').querySelector('span').textContent = data.total || 0;

            if (!items.length) {
                list.innerHTML = '';
                document.getElementById('libraryEmpty').style.display = '';
                return;
            }

            list.innerHTML = '';
            items.forEach(item => {
                const div = document.createElement('div');
                div.className = 'bank-question-item';
                div.innerHTML = `
                    <div class="bank-question-text">${escapeHtml(item.question_text)}</div>
                    <div class="bank-question-meta">
                        <span class="meta-item"><i class="bi bi-clock"></i> Saved ${timeSince(item.saved_at)}</span>
                    </div>
                    <div class="bank-question-actions">
                        <button class="bank-btn bank-btn-outline" onclick="BankLibrary.unsave(${item.id})" title="Remove from library">
                            <i class="bi bi-bookmark-x"></i> Remove
                        </button>
                    </div>`;
                list.appendChild(div);
            });

            renderPagination(
                document.getElementById('libraryPagination'),
                this.currentPage, data.pages || 1,
                (p) => { this.currentPage = p; this._load(); }
            );
        } catch (e) {
            list.innerHTML = `<div class="bank-empty"><i class="bi bi-exclamation-triangle"></i><h3>Could not load library</h3></div>`;
        }
    },

    async unsave(questionId) {
        try {
            await BankAPI.del(`/questions/${questionId}/save`, this.cfg.userId);
            bankToast('Removed from library', 'success');
            this._load();
        } catch (e) {
            bankToast(e.error || 'Could not remove', 'error');
        }
    }
};


/* ══════════════════════════════════════════
   BankNotifications
   ══════════════════════════════════════════ */
const BankNotifications = {
    cfg: {},
    currentPage: 1,

    init(cfg) {
        this.cfg = cfg;
        BankAPI.base = cfg.apiBase || '/api/v1/bank';
        this._load();
        document.getElementById('markAllReadBtn').addEventListener('click', () => this._markAllRead());
    },

    async _load() {
        const list = document.getElementById('notifList');
        list.innerHTML = Array(3).fill('<div class="bank-skeleton bank-skeleton-row"></div>').join('');
        document.getElementById('notifEmpty').style.display = 'none';

        try {
            const data = await BankAPI.get(`/notifications?page=${this.currentPage}&per_page=20`, this.cfg.userId);
            const items = data.items || [];
            const unread = data.unread_count || 0;

            document.getElementById('notifSubtitle').textContent =
                unread > 0 ? `${unread} unread notification${unread > 1 ? 's' : ''}` : 'All caught up!';

            if (unread > 0) {
                document.getElementById('markAllReadBtn').style.display = '';
            }

            if (!items.length) {
                list.innerHTML = '';
                document.getElementById('notifEmpty').style.display = '';
                return;
            }

            list.innerHTML = '';
            items.forEach(n => {
                const iconMap = {
                    question_approved: 'approved',
                    question_rejected: 'rejected',
                    badge_awarded: 'badge-award',
                    trust_granted: 'trust'
                };
                const iconClass = iconMap[n.type] || 'system';
                const iconChar = {
                    approved: 'bi-check-circle-fill',
                    rejected: 'bi-x-circle-fill',
                    'badge-award': 'bi-award-fill',
                    trust: 'bi-patch-check-fill',
                    system: 'bi-bell-fill'
                }[iconClass];

                const div = document.createElement('div');
                div.className = 'bank-notif' + (n.is_read ? '' : ' unread');
                div.innerHTML = `
                    <div class="bank-notif-icon ${iconClass}"><i class="bi ${iconChar}"></i></div>
                    <div class="bank-notif-body">
                        <div class="bank-notif-title">${escapeHtml(n.title)}</div>
                        <div class="bank-notif-msg">${escapeHtml(n.message)}</div>
                        <div class="bank-notif-time">${timeSince(n.created_at)}</div>
                    </div>`;

                if (!n.is_read) {
                    div.style.cursor = 'pointer';
                    div.addEventListener('click', () => this._markRead(n.id, div));
                }
                list.appendChild(div);
            });

            renderPagination(
                document.getElementById('notifPagination'),
                this.currentPage, data.pages || 1,
                (p) => { this.currentPage = p; this._load(); }
            );
        } catch (e) {
            list.innerHTML = `<div class="bank-empty"><i class="bi bi-exclamation-triangle"></i><h3>Could not load notifications</h3></div>`;
        }
    },

    async _markRead(id, el) {
        try {
            await BankAPI.post(`/notifications/${id}/read`, {}, this.cfg.userId);
            el.classList.remove('unread');
            el.style.cursor = '';
        } catch (e) { /* silent */ }
    },

    async _markAllRead() {
        try {
            await BankAPI.post('/notifications/read-all', {}, this.cfg.userId);
            bankToast('All marked as read', 'success');
            this._load();
        } catch (e) {
            bankToast(e.error || 'Could not mark all read', 'error');
        }
    }
};


/* ══════════════════════════════════════════
   BankLeaderboard
   ══════════════════════════════════════════ */
const BankLeaderboard = {
    cfg: {},
    currentPage: 1,

    init(cfg) {
        this.cfg = cfg;
        BankAPI.base = cfg.apiBase || '/api/v1/bank';
        this._load();
    },

    async _load() {
        const list = document.getElementById('lbList');
        list.innerHTML = Array(5).fill('<div class="bank-skeleton bank-skeleton-row"></div>').join('');
        const podium = document.getElementById('lbPodium');

        try {
            const data = await BankAPI.get(`/leaderboard?page=${this.currentPage}&per_page=20`, this.cfg.viewerUserId);
            const items = data.items || [];

            if (!items.length) {
                list.innerHTML = `<div class="bank-empty"><i class="bi bi-trophy"></i><h3>No contributors yet</h3>
                    <p>Be the first to contribute questions!</p></div>`;
                return;
            }

            // Top 3 podium cards
            if (this.currentPage === 1 && items.length >= 3) {
                podium.style.display = '';
                [0, 1, 2].forEach(i => {
                    const p = items[i];
                    const medals = ['🥇', '🥈', '🥉'];
                    const colors = ['#fbbf24', '#9ca3af', '#d97706'];
                    const el = document.getElementById(['lbFirst', 'lbSecond', 'lbThird'][i]);
                    const profileUrl = this.cfg.teacherProfileUrl.replace('__UID__', encodeURIComponent(p.id || p.user_id));
                    el.innerHTML = `
                        <a href="${profileUrl}" class="bank-profile-card d-block text-decoration-none" style="border-color:${colors[i]}40;">
                            <div style="font-size:2rem;margin-bottom:.5rem;">${medals[i]}</div>
                            <div class="bank-profile-avatar" style="width:56px;height:56px;font-size:1.4rem;margin-bottom:.75rem;">
                                ${escapeHtml((p.display_name || 'T')[0].toUpperCase())}
                            </div>
                            <div class="bank-profile-name" style="font-size:1rem;">${escapeHtml(p.display_name || 'Teacher')}</div>
                            <div style="font-size:.8rem;color:var(--bank-slate-600);margin-top:.25rem;">
                                ${p.questions_published || 0} published · ${Math.round(p.reputation_score || 0)} rep
                            </div>
                        </a>`;
                });
            }

            // Rows (skip first 3 on page 1)
            const startIdx = this.currentPage === 1 ? 3 : 0;
            const baseRank = (this.currentPage - 1) * 20;
            list.innerHTML = '';

            items.slice(startIdx).forEach((p, i) => {
                const rank = baseRank + startIdx + i + 1;
                const profileUrl = this.cfg.teacherProfileUrl.replace('__UID__', encodeURIComponent(p.id || p.user_id));
                const row = document.createElement('a');
                row.href = profileUrl;
                row.className = 'bank-leaderboard-row text-decoration-none';
                row.innerHTML = `
                    <div class="bank-lb-rank">#${rank}</div>
                    <div>
                        <div class="bank-lb-name">${escapeHtml(p.display_name || 'Teacher')}</div>
                        <div class="bank-lb-detail">${escapeHtml(p.contributor_rank || 'Newcomer')}</div>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-weight:700;color:var(--bank-slate-800);">${Math.round(p.reputation_score || 0)}</div>
                        <div class="bank-lb-detail">reputation</div>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-weight:600;color:var(--bank-teal);">${p.questions_published || 0}</div>
                        <div class="bank-lb-detail">published</div>
                    </div>`;
                list.appendChild(row);
            });

            renderPagination(
                document.getElementById('lbPagination'),
                this.currentPage, data.pages || 1,
                (p) => { this.currentPage = p; this._load(); }
            );
        } catch (e) {
            list.innerHTML = `<div class="bank-empty"><i class="bi bi-exclamation-triangle"></i><h3>Could not load leaderboard</h3></div>`;
        }
    }
};
