/**
 * Smart Paper Builder — State Manager & UI Controller
 * Dependencies: SortableJS, Bootstrap 5
 */
const Builder = (() => {
    'use strict';

    // ─── State ───────────────────────────────────────────────────
    const state = {
        config: {
            title: 'Home Test',
            class_id: null,
            subject_id: null,
            class_name: '',
            subject_name: '',
            time_minutes: 30,
            omr_style: true,
        },
        sections: [],
        selectedChapterIds: [],
    };

    let _bankPage = 1;
    let _bankHasMore = false;
    let _bankData = [];
    let _bankTargetSectionId = null;
    let _searchTimer = null;
    let _sectionSortable = null;
    let _questionSortables = {};
    let _newQTargetSection = null;
    let _uid = 0;
    const uid = () => 'u' + (++_uid);

    const CSRF = () => document.querySelector('meta[name="csrf-token"]')?.content || '';

    // ─── Init ────────────────────────────────────────────────────
    function init() {
        // Restore draft if available
        const draft = localStorage.getItem('prosno_builder_draft');
        if (draft) {
            try {
                const d = JSON.parse(draft);
                if (d.sections && d.sections.length) {
                    if (confirm('You have an unsaved paper draft. Restore it?')) {
                        Object.assign(state, d);
                        _applyConfigToUI();
                    }
                }
            } catch (e) { /* ignore */ }
        }

        // Default sections if empty
        if (!state.sections.length) {
            state.sections.push(
                _makeSection('mcq', 'ক-বিভাগ (বহুনির্বাচনী প্রশ্ন)'),
                _makeSection('sq', 'খ-বিভাগ (সংক্ষিপ্ত প্রশ্ন)'),
                _makeSection('cq', 'গ-বিভাগ (সৃজনশীল প্রশ্ন)')
            );
        }

        render();
        _initSectionSortable();
    }

    function _makeSection(type, title) {
        return {
            id: uid(),
            type: type,
            title: title,
            answer_count: null,   // null = all
            marks_per_question: type === 'mcq' ? 1 : type === 'sq' ? 2 : 10,
            questions: [],
        };
    }

    // ─── Config ──────────────────────────────────────────────────
    function updateConfig() {
        state.config.title = document.getElementById('cfgTitle')?.value || 'Home Test';
        state.config.time_minutes = parseInt(document.getElementById('cfgTime')?.value) || 30;
        state.config.omr_style = document.getElementById('cfgOmr')?.checked ?? true;
        _autoSave();
    }

    function onClassChange(classId) {
        state.config.class_id = classId ? parseInt(classId) : null;
        const sel = document.getElementById('cfgClass');
        state.config.class_name = sel?.options[sel.selectedIndex]?.text || '';

        const subjectSel = document.getElementById('cfgSubject');
        subjectSel.disabled = true;
        subjectSel.innerHTML = '<option value="">Loading...</option>';

        document.getElementById('chapterChips').innerHTML = '<span class="text-muted small">Select subject first</span>';
        state.selectedChapterIds = [];

        if (!classId) return;

        fetch(`/get-subjects/${classId}`)
            .then(r => r.json())
            .then(data => {
                subjectSel.innerHTML = '<option value="">-- Select Subject --</option>';
                (data.subjects || []).forEach(s => {
                    subjectSel.innerHTML += `<option value="${s.id}">${s.name_bn || s.name}</option>`;
                });
                subjectSel.disabled = false;
            })
            .catch(() => {
                subjectSel.innerHTML = '<option value="">Error loading</option>';
            });
    }

    function onSubjectChange(subjectId) {
        state.config.subject_id = subjectId ? parseInt(subjectId) : null;
        const sel = document.getElementById('cfgSubject');
        state.config.subject_name = sel?.options[sel.selectedIndex]?.text || '';

        const container = document.getElementById('chapterChips');
        container.innerHTML = '<span class="text-muted small">Loading chapters...</span>';
        state.selectedChapterIds = [];

        if (!subjectId) return;

        fetch(`/get-chapters/${subjectId}`)
            .then(r => r.json())
            .then(data => {
                const chapters = data.chapters || [];
                if (!chapters.length) {
                    container.innerHTML = '<span class="text-muted small">No chapters found</span>';
                    return;
                }
                container.innerHTML = chapters.map(ch =>
                    `<span class="chapter-chip" data-id="${ch.id}" onclick="Builder.toggleChapter(this, ${ch.id})">${ch.name_bn || ch.name}</span>`
                ).join('');
            })
            .catch(() => {
                container.innerHTML = '<span class="text-muted small">Error loading chapters</span>';
            });
    }

    function toggleChapter(el, chapId) {
        el.classList.toggle('active');
        const idx = state.selectedChapterIds.indexOf(chapId);
        if (idx === -1) {
            state.selectedChapterIds.push(chapId);
        } else {
            state.selectedChapterIds.splice(idx, 1);
        }
        // Auto-load bank
        if (state.selectedChapterIds.length > 0) {
            loadBank();
        }
    }

    function _applyConfigToUI() {
        const c = state.config;
        const el = (id) => document.getElementById(id);
        if (el('cfgTitle')) el('cfgTitle').value = c.title;
        if (el('cfgTime')) el('cfgTime').value = c.time_minutes;
        if (el('cfgOmr')) el('cfgOmr').checked = c.omr_style;
        // Class / subject / chapters need async restoring — skip for now
    }

    // ─── Render ──────────────────────────────────────────────────
    function render() {
        const container = document.getElementById('sectionsContainer');
        container.innerHTML = state.sections.map((sec, si) => _renderSection(sec, si)).join('');

        // Init sortables for each question list
        Object.keys(_questionSortables).forEach(k => {
            if (_questionSortables[k]) _questionSortables[k].destroy();
        });
        _questionSortables = {};

        state.sections.forEach(sec => {
            const listEl = document.getElementById('qlist_' + sec.id);
            if (listEl) {
                _questionSortables[sec.id] = new Sortable(listEl, {
                    group: 'questions',
                    animation: 200,
                    handle: '.q-drag',
                    ghostClass: 'sortable-ghost',
                    chosenClass: 'sortable-chosen',
                    onEnd: function (evt) {
                        _onQuestionDragEnd(evt);
                    },
                });
            }
        });

        _updateSummary();
    }

    function _renderSection(sec, index) {
        const iconMap = { mcq: 'bi-list-check', sq: 'bi-chat-square-text', cq: 'bi-file-earmark-text' };
        const totalMarks = _sectionMarks(sec);
        const qCount = sec.questions.length;

        let qListHtml = '';
        if (qCount === 0) {
            qListHtml = `<div class="section-empty"><i class="bi bi-plus-circle-dotted"></i><p>No questions yet. Add from the bank or write new ones.</p></div>`;
        } else {
            qListHtml = sec.questions.map((q, qi) => _renderQuestion(q, qi, sec)).join('');
        }

        return `
        <div class="section-card" data-section-id="${sec.id}">
            <div class="section-header" data-section-handle>
                <div class="section-header-left">
                    <span class="section-drag-handle"><i class="bi bi-grip-vertical"></i></span>
                    <span class="section-icon ${sec.type}"><i class="bi ${iconMap[sec.type] || 'bi-list'}"></i></span>
                    <div>
                        <h6 class="section-title">${_esc(sec.title)}</h6>
                        <span class="section-meta">${qCount} question${qCount !== 1 ? 's' : ''}</span>
                    </div>
                </div>
                <div class="section-header-right">
                    <span class="section-marks-badge">${totalMarks} marks</span>
                    <button class="section-delete" title="Delete section" onclick="Builder.deleteSection('${sec.id}')">
                        <i class="bi bi-trash3"></i>
                    </button>
                </div>
            </div>
            <div class="section-body" id="qlist_${sec.id}">
                ${qListHtml}
            </div>
            <div class="section-footer">
                <button class="btn btn-outline-primary btn-sm" onclick="Builder.openBankForSection('${sec.id}')">
                    <i class="bi bi-plus-lg me-1"></i> Add from Bank
                </button>
                <button class="btn btn-outline-secondary btn-sm" onclick="Builder.openNewQuestion('${sec.id}')">
                    <i class="bi bi-pencil me-1"></i> Write New
                </button>
            </div>
        </div>`;
    }

    function _renderQuestion(q, index, sec) {
        const num = index + 1;
        const text = q.question_text || q.stem || 'Question';
        const isDb = q.source === 'db';
        const sourceLabel = isDb ? 'DB' : 'Custom';
        const sourceClass = isDb ? 'db' : 'custom';
        const chapterLabel = q.chapter_name || '';
        const marks = sec.marks_per_question || 1;

        return `
        <div class="question-row" data-qid="${q._uid || ''}" data-source="${q.source}" data-db-id="${q.id || ''}">
            <span class="q-drag"><i class="bi bi-grip-vertical"></i></span>
            <span class="q-number">${num}.</span>
            <div class="q-content">
                <div class="q-content-text">${_esc(text)}</div>
                <div class="q-content-meta">
                    <span class="q-chip ${sourceClass}">${sourceLabel}</span>
                    ${chapterLabel ? `<span class="q-chip">${_esc(chapterLabel)}</span>` : ''}
                    <span class="q-chip">${marks}m</span>
                </div>
            </div>
            <button class="q-remove" onclick="Builder.removeQuestion('${sec.id}', ${index})" title="Remove">
                <i class="bi bi-x-lg"></i>
            </button>
        </div>`;
    }

    // ─── Section Operations ──────────────────────────────────────
    function addSection(type) {
        const titles = {
            mcq: 'ক-বিভাগ (বহুনির্বাচনী প্রশ্ন)',
            sq: 'খ-বিভাগ (সংক্ষিপ্ত প্রশ্ন)',
            cq: 'গ-বিভাগ (সৃজনশীল প্রশ্ন)',
        };
        state.sections.push(_makeSection(type, titles[type] || 'Custom Section'));
        render();
        _initSectionSortable();
        _autoSave();
    }

    function deleteSection(secId) {
        const sec = state.sections.find(s => s.id === secId);
        if (!sec) return;
        if (sec.questions.length > 0 && !confirm(`Delete "${sec.title}" with ${sec.questions.length} questions?`)) return;
        if (_bankTargetSectionId === secId) {
            _bankTargetSectionId = null;
        }
        state.sections = state.sections.filter(s => s.id !== secId);
        render();
        _initSectionSortable();
        _autoSave();
    }

    // ─── Question Operations ─────────────────────────────────────
    function removeQuestion(secId, index) {
        const sec = state.sections.find(s => s.id === secId);
        if (sec) {
            sec.questions.splice(index, 1);
            render();
            _initSectionSortable();
            _autoSave();
        }
    }

    function addQuestionToSection(secId, question) {
        const sec = state.sections.find(s => s.id === secId);
        if (!sec) return;

        // Prevent duplicates for DB questions
        if (question.source === 'db') {
            const exists = sec.questions.some(q => q.source === 'db' && q.id === question.id);
            if (exists) return;
        }

        question._uid = uid();
        sec.questions.push(question);
        render();
        _initSectionSortable();
        _autoSave();
        _updateBankAddButtons();
    }

    function _onQuestionDragEnd(evt) {
        // Rebuild questions array from DOM order
        state.sections.forEach(sec => {
            const listEl = document.getElementById('qlist_' + sec.id);
            if (!listEl) return;
            const rows = listEl.querySelectorAll('.question-row');
            const newQuestions = [];
            rows.forEach(row => {
                const quid = row.dataset.qid;
                const src = row.dataset.source;
                const dbId = row.dataset.dbId;
                // Find in any section
                for (const s of state.sections) {
                    const found = s.questions.find(q =>
                        (q._uid && q._uid === quid) ||
                        (src === 'db' && q.source === 'db' && String(q.id) === dbId)
                    );
                    if (found) {
                        newQuestions.push(found);
                        break;
                    }
                }
            });
            sec.questions = newQuestions;
        });
        render();
        _initSectionSortable();
        _autoSave();
    }

    // ─── Bank Panel ──────────────────────────────────────────────
    function loadBank() {
        _bankPage = 1;
        _bankData = [];
        _fetchBank();
    }

    function loadMoreBank() {
        _bankPage++;
        _fetchBank(true);
    }

    function searchBank() {
        clearTimeout(_searchTimer);
        _searchTimer = setTimeout(() => loadBank(), 350);
    }

    function _fetchBank(append = false) {
        if (!state.selectedChapterIds.length) {
            document.getElementById('bankList').innerHTML =
                '<div class="bank-empty"><i class="bi bi-inbox"></i><p>Select chapters first</p></div>';
            document.getElementById('bankFooter').style.display = 'none';
            return;
        }

        const type = document.getElementById('bankType')?.value || 'mcq';
        const difficulty = document.getElementById('bankDifficulty')?.value || '';
        const search = document.getElementById('bankSearch')?.value || '';

        if (!append) {
            document.getElementById('bankList').innerHTML =
                '<div class="bank-empty"><div class="spinner-border spinner-border-sm text-primary" role="status"></div><p class="mt-2">Loading...</p></div>';
        }

        fetch('/api/builder/questions', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': CSRF(),
            },
            body: JSON.stringify({
                chapter_ids: state.selectedChapterIds,
                question_types: [type],
                search: search,
                difficulty: difficulty,
                page: _bankPage,
                per_page: 20,
            }),
        })
            .then(r => r.json())
            .then(data => {
                const items = data[type] || [];
                const totalCount = (data.total_counts || {})[type] || 0;
                if (append) {
                    _bankData = _bankData.concat(items);
                } else {
                    _bankData = items;
                }
                _bankHasMore = _bankData.length < totalCount;
                _renderBank(type);
            })
            .catch(err => {
                console.error('Bank fetch error:', err);
                document.getElementById('bankList').innerHTML =
                    '<div class="bank-empty"><i class="bi bi-exclamation-triangle"></i><p>Error loading questions</p></div>';
            });
    }

    function _renderBank(type) {
        const container = document.getElementById('bankList');
        if (!_bankData.length) {
            container.innerHTML = '<div class="bank-empty"><i class="bi bi-search"></i><p>No questions found</p></div>';
            document.getElementById('bankFooter').style.display = 'none';
            return;
        }

        container.innerHTML = _bankData.map((q, i) => {
            const text = q.question_text || q.stem || '';
            const chapter = q.chapter_name || '';
            const diff = q.difficulty || '';
            const isAdded = _isQuestionInCanvas(q.id, type);

            return `
            <div class="bank-item" data-bank-idx="${i}">
                <div class="bank-item-text">${_esc(text)}</div>
                <div class="bank-item-meta">
                    <div class="bank-item-chips">
                        ${chapter ? `<span class="bank-item-chip">${_esc(chapter)}</span>` : ''}
                        ${diff ? `<span class="bank-item-chip">${diff}</span>` : ''}
                    </div>
                    <button class="bank-item-add ${isAdded ? 'added' : ''}"
                            data-bank-id="${q.id}"
                            onclick="Builder.addFromBank(${i}, '${type}')"
                            ${isAdded ? 'disabled' : ''}>
                        ${isAdded ? '✓ Added' : '+ Add'}
                    </button>
                </div>
            </div>`;
        }).join('');

        document.getElementById('bankFooter').style.display = _bankHasMore ? 'block' : 'none';
    }

    function addFromBank(bankIdx, type) {
        const q = _bankData[bankIdx];
        if (!q) return;

        // Prefer the section the user opened the bank from.
        let sec = state.sections.find(s => s.id === _bankTargetSectionId && s.type === type);
        if (!sec) {
            sec = state.sections.find(s => s.type === type);
        }
        if (!sec) {
            // Create a section for this type
            addSection(type);
            sec = state.sections.find(s => s.type === type);
        }
        if (!sec) return;
        _bankTargetSectionId = sec.id;

        const question = {
            source: 'db',
            db_source: q.db_source || 'bank',
            id: q.id,
            question_text: q.question_text || q.stem || '',
            answer_options: q.answer_options || [],
            correct_answer: q.correct_answer || '',
            type: q.type || 'simple',
            sub_options: q.sub_options || [],
            final_prompt: q.final_prompt || '',
            chapter_name: q.chapter_name || '',
            marks: q.marks || q.total_marks || undefined,
            stem: q.stem || '',
            parts: q.parts || [],
        };

        addQuestionToSection(sec.id, question);
    }

    function openBankForSection(secId) {
        const sec = state.sections.find(s => s.id === secId);
        if (sec) {
            _bankTargetSectionId = secId;
            document.getElementById('bankType').value = sec.type;
        }
        // On mobile, open the bank panel
        const panel = document.getElementById('bankPanel');
        if (window.innerWidth < 992) {
            panel.classList.add('open');
        }
        if (state.selectedChapterIds.length > 0) {
            loadBank();
        }
    }

    function toggleBank() {
        const panel = document.getElementById('bankPanel');
        panel.classList.toggle('open');
    }

    function _isQuestionInCanvas(dbId, type) {
        return state.sections
            .filter(s => s.type === type)
            .some(s => s.questions.some(q => q.source === 'db' && q.id === dbId));
    }

    function _updateBankAddButtons() {
        const type = document.getElementById('bankType')?.value || 'mcq';
        document.querySelectorAll('.bank-item-add').forEach(btn => {
            const bId = parseInt(btn.dataset.bankId);
            const added = _isQuestionInCanvas(bId, type);
            btn.classList.toggle('added', added);
            btn.disabled = added;
            btn.textContent = added ? '✓ Added' : '+ Add';
        });
    }

    // ─── Write New Question ──────────────────────────────────────
    function openNewQuestion(secId) {
        _newQTargetSection = secId;
        const sec = state.sections.find(s => s.id === secId);
        if (!sec) return;

        // Show appropriate form
        document.getElementById('newQFormMCQ').style.display = sec.type === 'mcq' ? '' : 'none';
        document.getElementById('newQFormSQ').style.display = sec.type === 'sq' ? '' : 'none';

        // Clear fields
        ['nqText', 'nqOpt1', 'nqOpt2', 'nqOpt3', 'nqOpt4', 'nqSqText'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.value = '';
        });

        new bootstrap.Modal(document.getElementById('newQuestionModal')).show();
    }

    function addCustomQuestion() {
        const sec = state.sections.find(s => s.id === _newQTargetSection);
        if (!sec) return;

        if (sec.type === 'mcq') {
            const text = document.getElementById('nqText').value.trim();
            if (!text) { alert('Question text is required.'); return; }
            const opts = [
                document.getElementById('nqOpt1').value.trim(),
                document.getElementById('nqOpt2').value.trim(),
                document.getElementById('nqOpt3').value.trim(),
                document.getElementById('nqOpt4').value.trim(),
            ];
            const answer = document.getElementById('nqAnswer').value;

            addQuestionToSection(sec.id, {
                source: 'custom',
                question_text: text,
                answer_options: opts,
                correct_answer: answer,
                type: 'simple',
            });
        } else if (sec.type === 'sq') {
            const text = document.getElementById('nqSqText').value.trim();
            if (!text) { alert('Question text is required.'); return; }
            const marks = parseInt(document.getElementById('nqSqMarks').value) || 2;

            addQuestionToSection(sec.id, {
                source: 'custom',
                question_text: text,
                marks: marks,
            });
        }

        bootstrap.Modal.getInstance(document.getElementById('newQuestionModal'))?.hide();
    }

    // ─── Summary ─────────────────────────────────────────────────
    function _updateSummary() {
        let mcqCount = 0, sqCount = 0, cqCount = 0, totalMarks = 0;
        state.sections.forEach(sec => {
            const n = sec.questions.length;
            if (sec.type === 'mcq') {
                mcqCount += n;
                totalMarks += n * (sec.marks_per_question || 1);
            } else if (sec.type === 'sq') {
                sqCount += n;
                const answerN = sec.answer_count || n;
                totalMarks += answerN * (sec.marks_per_question || 2);
            } else if (sec.type === 'cq') {
                cqCount += n;
                const answerN = sec.answer_count || n;
                totalMarks += answerN * (sec.marks_per_question || 10);
            }
        });

        document.getElementById('totalMCQ').textContent = mcqCount;
        document.getElementById('totalSQ').textContent = sqCount;
        document.getElementById('totalCQ').textContent = cqCount;
        document.getElementById('totalMarks').textContent = totalMarks;
    }

    function _sectionMarks(sec) {
        const n = sec.questions.length;
        return n * (sec.marks_per_question || 1);
    }

    // ─── Generate ────────────────────────────────────────────────
    function generate(format = 'docx') {
        const totalQ = state.sections.reduce((s, sec) => s + sec.questions.length, 0);
        if (totalQ === 0) {
            alert('Please add at least one question to generate a paper.');
            return;
        }

        const btn = document.getElementById('generateBtn');
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Generating...';

        // Build sections payload
        const secs = state.sections.filter(s => s.questions.length > 0).map(sec => ({
            type: sec.type,
            title: sec.title,
            answer_count: sec.answer_count || sec.questions.length,
            marks_per_question: sec.marks_per_question,
            questions: sec.questions.map(q => {
                if (q.source === 'db') {
                    return { source: 'db', db_source: q.db_source || 'bank', id: q.id };
                }
                return {
                    source: 'custom',
                    question_text: q.question_text || '',
                    answer_options: q.answer_options || [],
                    correct_answer: q.correct_answer || '',
                    type: q.type || 'simple',
                    sub_options: q.sub_options || [],
                    final_prompt: q.final_prompt || '',
                    marks: q.marks || undefined,
                    stem: q.stem || '',
                    parts: q.parts || [],
                };
            }),
        }));

        const payload = {
            paper_config: {
                title: state.config.title,
                class_id: state.config.class_id,
                subject_id: state.config.subject_id,
                class_name: state.config.class_name,
                subject_name: state.config.subject_name,
                time_minutes: state.config.time_minutes,
                omr_style: state.config.omr_style,
            },
            sections: secs,
            format: format,
        };

        fetch('/api/builder/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': CSRF(),
            },
            body: JSON.stringify(payload),
        })
            .then(r => r.json())
            .then(data => {
                btn.disabled = false;
                btn.innerHTML = '<i class="bi bi-file-earmark-word me-1"></i> Generate DOCX';

                if (data.error) {
                    alert('Error: ' + data.error);
                    return;
                }

                // Show result card
                document.getElementById('resultCard').style.display = '';
                document.getElementById('resultCount').textContent = data.question_count;
                document.getElementById('resultMarks').textContent = data.total_marks;
                document.getElementById('dlStudent').href = data.student_download;
                document.getElementById('dlTeacher').href = data.teacher_download;
                document.getElementById('resultCard').scrollIntoView({ behavior: 'smooth' });
            })
            .catch(err => {
                console.error('Generate error:', err);
                btn.disabled = false;
                btn.innerHTML = '<i class="bi bi-file-earmark-word me-1"></i> Generate DOCX';
                alert('Failed to generate paper. Please try again.');
            });
    }

    // ─── Sortable Init ──────────────────────────────────────────
    function _initSectionSortable() {
        if (_sectionSortable) _sectionSortable.destroy();
        const container = document.getElementById('sectionsContainer');
        if (!container) return;
        _sectionSortable = new Sortable(container, {
            animation: 250,
            handle: '[data-section-handle]',
            ghostClass: 'sortable-ghost',
            onEnd: function (evt) {
                // Reorder state.sections
                const moved = state.sections.splice(evt.oldIndex, 1)[0];
                state.sections.splice(evt.newIndex, 0, moved);
                render();
                _initSectionSortable();
                _autoSave();
            },
        });
    }

    // ─── Draft / Auto-save ───────────────────────────────────────
    function _autoSave() {
        try {
            localStorage.setItem('prosno_builder_draft', JSON.stringify(state));
        } catch (e) { /* quota */ }
    }

    function saveDraft() {
        _autoSave();
        const ind = document.getElementById('draftIndicator');
        if (ind) {
            ind.style.display = '';
            setTimeout(() => { ind.style.display = 'none'; }, 2200);
        }
    }

    // ─── Preview Toggle ─────────────────────────────────────────
    function togglePreview() {
        // Minimal: for now, scroll to summary
        document.getElementById('summaryBar')?.scrollIntoView({ behavior: 'smooth' });
    }

    // ─── Helpers ─────────────────────────────────────────────────
    function _esc(s) {
        if (!s) return '';
        const div = document.createElement('div');
        div.textContent = s;
        return div.innerHTML;
    }

    // ─── Public API ──────────────────────────────────────────────
    return {
        init,
        updateConfig,
        onClassChange,
        onSubjectChange,
        toggleChapter,
        addSection,
        deleteSection,
        removeQuestion,
        addQuestionToSection,
        loadBank,
        loadMoreBank,
        searchBank,
        addFromBank,
        openBankForSection,
        toggleBank,
        openNewQuestion,
        addCustomQuestion,
        generate,
        saveDraft,
        togglePreview,
    };
})();

// ─── Auto-init on page load ─────────────────────────────────
document.addEventListener('DOMContentLoaded', Builder.init);
