(function () {
    'use strict';

    const boot = window.OMR_BUILDER_DATA || {};
    const defaultConfig = deepClone(boot.defaultConfig || {});
    const layouts = boot.layouts || {};
    const themes = boot.themes || {};
    const bubbleSizes = boot.bubbleSizes || {};
    const initialTemplateId = boot.initialTemplateId || null;
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

    const state = {
        templateId: null,
        templates: [],
        dirty: false,
        name: '',
        config: deepClone(defaultConfig),
    };

    const els = {};
    const bnDigits = { 0: '০', 1: '১', 2: '২', 3: '৩', 4: '৪', 5: '৫', 6: '৬', 7: '৭', 8: '৮', 9: '৯' };
    const optionLabels = ['ক', 'খ', 'গ', 'ঘ'];

    document.addEventListener('DOMContentLoaded', init);

    function init() {
        cacheDom();
        bindEvents();
        resetToDefault(false);
        loadTemplates().then(async function () {
            if (initialTemplateId) {
                await loadTemplate(initialTemplateId);
            } else {
                render();
            }
        });
    }

    function cacheDom() {
        const ids = [
            'omrTemplateName',
            'omrTemplateSelect',
            'omrTemplateMeta',
            'omrQuestionCountLabel',
            'omrPreviewSheet',
            'omrScanStatus',
            'omrDownloadBtn',
            'omrNewTemplateBtn',
            'omrSaveTemplateBtn',
            'omrDuplicateTemplateBtn',
            'omrDeleteTemplateBtn',
            'omrLoadTemplateBtn',
            'omrInstitutionInput',
            'omrTitleInput',
            'omrSubtitleInput',
            'omrFieldRoll',
            'omrFieldSetCode',
            'omrFieldSubjectCode',
        ];
        ids.forEach(function (id) {
            els[id] = document.getElementById(id);
        });
        els.instructions = Array.from(document.querySelectorAll('.omr-instruction-input'));
    }

    function bindEvents() {
        els.omrTemplateName.addEventListener('input', function () {
            state.name = els.omrTemplateName.value;
            markDirty();
        });

        [
            els.omrInstitutionInput,
            els.omrTitleInput,
            els.omrSubtitleInput,
            els.omrFieldRoll,
            els.omrFieldSetCode,
            els.omrFieldSubjectCode,
            ...els.instructions,
        ].forEach(function (element) {
            element.addEventListener('input', syncFromControls);
            element.addEventListener('change', syncFromControls);
        });

        document.querySelectorAll('[data-question-count]').forEach(function (button) {
            button.addEventListener('click', function () {
                state.config.question_count = parseInt(button.dataset.questionCount, 10);
                applyStateToControls();
                markDirty();
                render();
            });
        });

        document.querySelectorAll('[data-bubble-size]').forEach(function (button) {
            button.addEventListener('click', function () {
                state.config.bubble_size = button.dataset.bubbleSize;
                applyStateToControls();
                markDirty();
                render();
            });
        });

        document.querySelectorAll('[data-header-mode]').forEach(function (button) {
            button.addEventListener('click', function () {
                state.config.header_mode = button.dataset.headerMode;
                applyStateToControls();
                markDirty();
                render();
            });
        });

        document.querySelectorAll('[data-theme-color]').forEach(function (button) {
            button.addEventListener('click', function () {
                state.config.theme_color = button.dataset.themeColor;
                applyStateToControls();
                markDirty();
                render();
            });
        });

        els.omrDownloadBtn.addEventListener('click', downloadPdf);
        els.omrNewTemplateBtn.addEventListener('click', function () {
            resetToDefault(true);
        });
        els.omrSaveTemplateBtn.addEventListener('click', saveTemplate);
        els.omrDuplicateTemplateBtn.addEventListener('click', duplicateTemplate);
        els.omrDeleteTemplateBtn.addEventListener('click', deleteTemplate);
        els.omrLoadTemplateBtn.addEventListener('click', function () {
            const id = parseInt(els.omrTemplateSelect.value, 10);
            if (!id) {
                showToast('Select a template to load.', 'warning');
                return;
            }
            loadTemplate(id);
        });
    }

    function resetToDefault(clearSelection) {
        state.templateId = null;
        state.config = deepClone(defaultConfig);
        state.name = `OMR Template ${state.config.question_count}`;
        state.dirty = false;
        if (clearSelection) {
            els.omrTemplateSelect.value = '';
        }
        applyStateToControls();
        render();
    }

    function deepClone(value) {
        if (window.structuredClone) {
            return window.structuredClone(value);
        }
        return JSON.parse(JSON.stringify(value));
    }

    function markDirty() {
        state.dirty = true;
        updateMeta();
    }

    function syncFromControls() {
        state.name = els.omrTemplateName.value.trim();
        state.config.header.institution = els.omrInstitutionInput.value.trim();
        state.config.header.title = els.omrTitleInput.value.trim();
        state.config.header.subtitle = els.omrSubtitleInput.value.trim();
        state.config.fields.roll = els.omrFieldRoll.checked;
        state.config.fields.set_code = els.omrFieldSetCode.checked;
        state.config.fields.subject_code = els.omrFieldSubjectCode.checked;

        if (!state.config.fields.roll && !state.config.fields.set_code && !state.config.fields.subject_code) {
            state.config.fields.roll = true;
            els.omrFieldRoll.checked = true;
            showToast('At least one student info block must remain enabled.', 'warning');
        }

        state.config.instructions = els.instructions
            .map(function (input) { return input.value.trim(); })
            .filter(Boolean);

        if (!state.config.instructions.length) {
            state.config.instructions = deepClone(defaultConfig.instructions || []);
        }

        markDirty();
        render();
    }

    function applyStateToControls() {
        els.omrTemplateName.value = state.name || '';
        els.omrInstitutionInput.value = state.config.header.institution || '';
        els.omrTitleInput.value = state.config.header.title || '';
        els.omrSubtitleInput.value = state.config.header.subtitle || '';
        els.omrFieldRoll.checked = !!state.config.fields.roll;
        els.omrFieldSetCode.checked = !!state.config.fields.set_code;
        els.omrFieldSubjectCode.checked = !!state.config.fields.subject_code;

        els.instructions.forEach(function (input, index) {
            input.value = state.config.instructions[index] || '';
        });

        setActiveState('[data-question-count]', 'questionCount', String(state.config.question_count));
        setActiveState('[data-bubble-size]', 'bubbleSize', state.config.bubble_size);
        setActiveState('[data-header-mode]', 'headerMode', state.config.header_mode);
        setActiveState('[data-theme-color]', 'themeColor', state.config.theme_color);

        if (state.templateId) {
            els.omrTemplateSelect.value = String(state.templateId);
            els.omrSaveTemplateBtn.textContent = 'Update';
        } else {
            els.omrTemplateSelect.value = '';
            els.omrSaveTemplateBtn.textContent = 'Save';
        }
        updateMeta();
    }

    function setActiveState(selector, key, value) {
        document.querySelectorAll(selector).forEach(function (button) {
            const dataKey = 'data-' + key.replace(/[A-Z]/g, function (match) {
                return '-' + match.toLowerCase();
            });
            button.classList.toggle('active', button.getAttribute(dataKey) === value);
        });
    }

    async function loadTemplates() {
        try {
            const response = await fetch('/api/omr/templates');
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || 'Failed to load templates.');
            }
            state.templates = data.templates || [];
            populateTemplateSelect();
        } catch (error) {
            showToast(error.message, 'error');
        }
    }

    function populateTemplateSelect() {
        const currentValue = state.templateId ? String(state.templateId) : '';
        els.omrTemplateSelect.innerHTML = '<option value="">Select a saved template</option>';
        state.templates.forEach(function (template) {
            const option = document.createElement('option');
            option.value = template.id;
            option.textContent = template.name + ' (' + template.question_count + ')';
            els.omrTemplateSelect.appendChild(option);
        });
        els.omrTemplateSelect.value = currentValue;
    }

    async function loadTemplate(id) {
        try {
            const response = await fetch('/api/omr/templates/' + id);
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || 'Failed to load template.');
            }
            const template = data.template;
            state.templateId = template.id;
            state.name = template.name;
            state.config = deepClone(template.config_json);
            state.dirty = false;
            applyStateToControls();
            render();
            showToast('Template loaded.', 'success');
        } catch (error) {
            showToast(error.message, 'error');
        }
    }

    async function saveTemplate() {
        syncFromControls();
        const payload = {
            name: state.name || `OMR Template ${state.config.question_count}`,
            config_json: state.config,
        };
        const url = state.templateId ? '/api/omr/templates/' + state.templateId : '/api/omr/templates';
        const method = state.templateId ? 'PUT' : 'POST';

        try {
            const response = await fetch(url, {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                },
                body: JSON.stringify(payload),
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || 'Failed to save template.');
            }
            state.templateId = data.template.id;
            state.name = data.template.name;
            state.config = deepClone(data.template.config_json);
            state.dirty = false;
            await loadTemplates();
            applyStateToControls();
            render();
            showToast(state.templateId ? 'Template saved.' : 'Template created.', 'success');
        } catch (error) {
            showToast(error.message, 'error');
        }
    }

    function duplicateTemplate() {
        syncFromControls();
        state.templateId = null;
        state.name = (state.name || 'OMR Template') + ' Copy';
        state.dirty = true;
        applyStateToControls();
        render();
        showToast('Duplicate ready as a new draft.', 'success');
    }

    async function deleteTemplate() {
        if (!state.templateId) {
            resetToDefault(true);
            showToast('Draft cleared.', 'success');
            return;
        }
        if (!window.confirm('Delete this saved OMR template?')) {
            return;
        }
        try {
            const response = await fetch('/api/omr/templates/' + state.templateId + '/delete', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                },
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || 'Failed to delete template.');
            }
            resetToDefault(true);
            await loadTemplates();
            showToast('Template deleted.', 'success');
        } catch (error) {
            showToast(error.message, 'error');
        }
    }

    async function downloadPdf() {
        syncFromControls();
        const payload = {
            template_id: state.templateId,
            name: state.name || `OMR Template ${state.config.question_count}`,
            config_json: state.config,
        };
        const button = els.omrDownloadBtn;
        const original = button.innerHTML;
        button.disabled = true;
        button.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Generating';

        try {
            const response = await fetch('/api/omr/render', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                },
                body: JSON.stringify(payload),
            });
            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.error || 'Failed to generate PDF.');
            }
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const anchor = document.createElement('a');
            anchor.href = url;
            anchor.download = slugify(payload.name) + '.pdf';
            document.body.appendChild(anchor);
            anchor.click();
            anchor.remove();
            URL.revokeObjectURL(url);
            showToast('PDF downloaded.', 'success');
            await loadTemplates();
        } catch (error) {
            showToast(error.message, 'error');
        } finally {
            button.disabled = false;
            button.innerHTML = original;
        }
    }

    function render() {
        renderPreview();
        updateMeta();
        els.omrQuestionCountLabel.innerHTML = '<i class="bi bi-ui-checks-grid"></i> ' + state.config.question_count + ' questions';
    }

    function renderPreview() {
        const theme = themes[state.config.theme_color] || { hex: '#f45d74' };
        const layout = layouts[String(state.config.question_count)] || layouts[state.config.question_count];
        const accentHex = theme.hex;
        const soft = hexToRgba(accentHex, 0.16);
        const lighter = hexToRgba(accentHex, 0.08);

        els.omrPreviewSheet.style.setProperty('--omr-accent', accentHex);
        els.omrPreviewSheet.style.setProperty('--omr-accent-soft', soft);
        els.omrPreviewSheet.style.setProperty('--omr-accent-light', lighter);

        const blocks = [];
        blocks.push(renderMarkers());
        blocks.push(renderHeader());
        blocks.push(renderIdentitySection());
        blocks.push(renderAnswers(layout));
        blocks.push('<div class="omr-preview-footer-badge" style="' + boxStyle(134, 276, 62, 12) + '"><i class="bi bi-check-circle-fill"></i><span>Scannable</span></div>');
        els.omrPreviewSheet.innerHTML = blocks.join('');
    }

    function renderMarkers() {
        const positions = [
            ['tl', 2.5, 279],
            ['tr', 197.5, 279],
            ['bl', 2.5, 12],
            ['br', 197.5, 12],
            ['ml', 2.5, 148],
            ['mr', 197.5, 148],
        ];
        return positions.map(function (item) {
            return '<div class="omr-preview-marker omr-preview-marker-' + item[0] + '" style="' + boxStyle(item[1], item[2], 10, 10) + '"><span></span></div>';
        }).join('');
    }

    function renderHeader() {
        if (state.config.header_mode === 'manual') {
            return '<div class="omr-preview-header omr-preview-header-manual" style="' + boxStyle(14, 10, 182, 30) + '">' +
                '<div class="omr-preview-line"><strong>প্রতিষ্ঠান</strong><span></span></div>' +
                '<div class="omr-preview-line"><strong>পরীক্ষার নাম</strong><span></span></div>' +
                '<div class="omr-preview-line"><strong>উপশিরোনাম</strong><span></span></div>' +
                '</div>';
        }

        return '<div class="omr-preview-header" style="' + boxStyle(14, 10, 182, 30) + '">' +
            '<p class="omr-preview-warning">এই বক্সে কোনও দাগ দেওয়া যাবে না</p>' +
            '<h2>' + escapeHtml(state.config.header.title || 'OMR Sheet') + '</h2>' +
            '<p class="omr-preview-subtitle">' + escapeHtml(state.config.header.subtitle || '') + '</p>' +
            '<p class="omr-preview-institution">' + escapeHtml(state.config.header.institution || '') + '</p>' +
            '</div>';
    }

    function renderIdentitySection() {
        const html = [];
        if (state.config.fields.roll) {
            html.push(renderMatrixBlock({
                title: 'রোল নম্বর',
                x: 14,
                y: 52,
                w: 42,
                h: 82,
                cols: 6,
                labels: ['০', '১', '২', '৩', '৪', '৫', '৬', '৭', '৮', '৯'],
            }));
        }
        if (state.config.fields.subject_code) {
            html.push(renderMatrixBlock({
                title: 'বিষয় কোড',
                x: 59,
                y: 52,
                w: 38,
                h: 82,
                cols: 3,
                labels: ['০', '১', '২', '৩', '৪', '৫', '৬', '৭', '৮', '৯'],
            }));
        }
        if (state.config.fields.set_code) {
            html.push(renderMatrixBlock({
                title: 'সেট কোড',
                x: 100,
                y: 52,
                w: 20,
                h: 82,
                cols: 1,
                labels: optionLabels,
            }));
        }

        html.push('<div class="omr-preview-instructions" style="' + boxStyle(125, 52, 70, 40) + '">' +
            '<div class="omr-preview-card-title">নির্দেশনা</div>' +
            '<ol>' + state.config.instructions.slice(0, 6).map(function (instruction) {
                return '<li>' + escapeHtml(instruction) + '</li>';
            }).join('') + '</ol></div>');
        html.push('<div class="omr-preview-signature" style="' + boxStyle(125, 97, 46, 23) + '">কক্ষ পরিদর্শকের স্বাক্ষর</div>');
        return html.join('');
    }

    function renderMatrixBlock(spec) {
        const rows = spec.labels.length;
        const bubbleClass = state.config.bubble_size === 'small' ? 'small' : 'large';
        let cells = '';
        for (let col = 0; col < spec.cols; col += 1) {
            spec.labels.forEach(function (label) {
                cells += '<div class="omr-preview-matrix-cell"><span class="omr-mini-bubble ' + bubbleClass + '">' + escapeHtml(label) + '</span></div>';
            });
        }

        return '<div class="omr-preview-card" style="' + boxStyle(spec.x, spec.y, spec.w, spec.h) + '">' +
            '<div class="omr-preview-card-title">' + spec.title + '</div>' +
            '<div class="omr-preview-matrix" style="grid-template-columns: repeat(' + spec.cols + ', 1fr); grid-template-rows: repeat(' + rows + ', 1fr);">' +
            cells +
            '</div></div>';
    }

    function renderAnswers(layout) {
        const grid = layout.answer_grid;
        const total = state.config.question_count;
        const titleStyle = boxStyle(40, grid.y_mm - 13, 130, 8);
        let html = '<div class="omr-preview-answer-title" style="' + titleStyle + '">বহুনির্বাচনি অভীক্ষার উত্তরপত্র</div>';

        for (let columnIndex = 0; columnIndex < grid.columns; columnIndex += 1) {
            const x = grid.x_mm + (columnIndex * (grid.column_width_mm + grid.column_gap_mm));
            const y = grid.y_mm;
            const height = grid.header_height_mm + (grid.rows * grid.row_height_mm);
            const headerPct = percent(grid.header_height_mm, height);
            const rowsPct = (100 - parseFloat(headerPct)).toFixed(4);
            const startNumber = (columnIndex * grid.rows) + 1;
            const endNumber = Math.min(total, startNumber + grid.rows - 1);
            html += '<div class="omr-preview-answer-column" style="' + boxStyle(x, y, grid.column_width_mm, height) + '">' +
                '<div class="omr-preview-answer-header" style="height:' + headerPct + '%">' +
                '<span class="question-label" style="width:' + percent(grid.number_width_mm, grid.column_width_mm) + '%">প্রশ্ন</span>' +
                '<span class="answer-label">উত্তর</span>' +
                '</div>' +
                '<div class="omr-preview-answer-rows" style="height:' + rowsPct + '%">';

            for (let rowIndex = 0; rowIndex < grid.rows; rowIndex += 1) {
                const number = startNumber + rowIndex;
                html += '<div class="omr-preview-answer-row">' +
                    '<span class="omr-preview-qnum" style="width:' + percent(grid.number_width_mm, grid.column_width_mm) + '%">' + (number <= endNumber ? toBanglaNumber(number) : '&nbsp;') + '</span>' +
                    '<div class="omr-preview-options">';
                optionLabels.forEach(function (label) {
                    html += '<span class="omr-preview-option"><span class="omr-mini-bubble ' + state.config.bubble_size + '">' + label + '</span></span>';
                });
                html += '</div></div>';
            }

            html += '</div></div>';
        }
        return html;
    }

    function updateMeta() {
        if (!els.omrTemplateMeta) {
            return;
        }
        if (state.templateId) {
            els.omrTemplateMeta.textContent = state.dirty
                ? 'Saved template with unsaved changes'
                : 'Saved template #' + state.templateId;
        } else {
            els.omrTemplateMeta.textContent = state.dirty ? 'Unsaved draft' : 'Ready for a new template';
        }
    }

    function boxStyle(x, y, width, height) {
        return [
            'left:' + percent(x, 210) + '%',
            'top:' + percent(y, 297) + '%',
            'width:' + percent(width, 210) + '%',
            'height:' + percent(height, 297) + '%',
        ].join(';');
    }

    function percent(value, total) {
        return ((value / total) * 100).toFixed(4);
    }

    function toBanglaNumber(value) {
        return String(value).split('').map(function (digit) {
            return bnDigits[digit] || digit;
        }).join('');
    }

    function hexToRgba(hex, alpha) {
        const clean = hex.replace('#', '');
        const normalized = clean.length === 3 ? clean.split('').map(function (char) {
            return char + char;
        }).join('') : clean;
        const value = parseInt(normalized, 16);
        const r = (value >> 16) & 255;
        const g = (value >> 8) & 255;
        const b = value & 255;
        return 'rgba(' + r + ', ' + g + ', ' + b + ', ' + alpha + ')';
    }

    function slugify(text) {
        return (text || 'omr-template')
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, '-')
            .replace(/^-+|-+$/g, '') || 'omr-template';
    }

    function escapeHtml(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function showToast(message, type) {
        const colorMap = {
            success: '#10b981',
            warning: '#f59e0b',
            error: '#ef4444',
        };
        const toast = document.createElement('div');
        toast.className = 'omr-floating-toast';
        toast.style.background = colorMap[type] || colorMap.success;
        toast.textContent = message;
        document.body.appendChild(toast);
        requestAnimationFrame(function () {
            toast.classList.add('show');
        });
        window.setTimeout(function () {
            toast.classList.remove('show');
            window.setTimeout(function () {
                toast.remove();
            }, 250);
        }, 2200);
    }
})();
