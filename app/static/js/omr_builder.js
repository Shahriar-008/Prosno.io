(function () {
    'use strict';

    const boot = window.OMR_BUILDER_DATA || {};
    const defaultConfig = deepClone(boot.defaultConfig || {});
    const generalRules = Object.assign({
        min_question_count: 1,
        max_question_count: 100,
        supported_columns: [1, 2, 3, 4],
        max_question_count_by_column: { 1: 100, 2: 50, 3: 75, 4: 100 },
    }, boot.generalRules || {});
    const generalAutoFlowColumn = 1;
    const generalMaxRowsPerAutoColumn = 25;
    const generalAnswerMarkerBandHeightMm = 5.2;
    const layouts = boot.layouts || {};
    const themes = boot.themes || {};
    const bubbleSizes = boot.bubbleSizes || {};
    const initialTemplateId = boot.initialTemplateId || null;
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
    const generalColumnLayouts = {
        1: {
            x_mm: 52,
            column_width_mm: 106,
            column_gap_mm: 0,
            header_height_mm: 8.6,
            number_width_mm: 16.5,
            max_row_height_mm: 13.2,
        },
        2: {
            x_mm: 35,
            column_width_mm: 67,
            column_gap_mm: 6,
            header_height_mm: 8.2,
            number_width_mm: 13.2,
            max_row_height_mm: 10.2,
        },
        3: {
            x_mm: 25,
            column_width_mm: 50,
            column_gap_mm: 5,
            header_height_mm: 7.6,
            number_width_mm: 11,
            max_row_height_mm: 8.4,
        },
        4: {
            x_mm: 13,
            column_width_mm: 43,
            column_gap_mm: 4,
            header_height_mm: 7.1,
            number_width_mm: 9.4,
            max_row_height_mm: 6.45,
        },
    };

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

    const digitLabels = ['০', '১', '২', '৩', '৪', '৫', '৬', '৭', '৮', '৯'];
    const omrCopy = Object.freeze({
        warning: 'এই বক্সে কোনো দাগ দেওয়া যাবে না',
        institutionalAnswerTitle: 'বহুনির্বাচনি অভীক্ষার উত্তরপত্র',
        generalAnswerTitle: 'সাধারণ বহুনির্বাচনি উত্তরপত্র',
        question: 'প্রশ্ন',
        answer: 'উত্তর',
        rollNumber: 'রোল নম্বর',
        subjectCode: 'বিষয় কোড',
        setCode: 'সেট কোড',
        instructions: 'নির্দেশনা',
        signature: 'কক্ষ পরিদর্শকের স্বাক্ষর',
        institution: 'প্রতিষ্ঠান',
        examName: 'পরীক্ষার নাম',
        subtitle: 'উপশিরোনাম',
        name: 'নাম',
        className: 'শ্রেণি',
        section: 'সেকশন',
        subject: 'বিষয়',
        roll: 'রোল',
    });

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
            'omrVariantLabel',
            'omrQuestionCountLabel',
            'omrColumnCountLabel',
            'omrPreviewSheet',
            'omrScanStatus',
            'omrScanStatusText',
            'omrDownloadBtn',
            'omrNewTemplateBtn',
            'omrSaveTemplateBtn',
            'omrDuplicateTemplateBtn',
            'omrDeleteTemplateBtn',
            'omrLoadTemplateBtn',
            'omrInstitutionInput',
            'omrTitleInput',
            'omrSubtitleInput',
            'omrCustomQuestionCount',
            'omrFieldRoll',
            'omrFieldSetCode',
            'omrFieldSubjectCode',
            'omrPresetLayoutControls',
            'omrGeneralLayoutControls',
            'omrHeaderModeGroup',
            'omrFieldsPanel',
            'omrInstructionsPanel',
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
            els.omrCustomQuestionCount,
            els.omrFieldRoll,
            els.omrFieldSetCode,
            els.omrFieldSubjectCode,
            ...els.instructions,
        ].forEach(function (element) {
            if (!element) {
                return;
            }
            element.addEventListener('input', syncFromControls);
            element.addEventListener('change', syncFromControls);
        });

        document.querySelectorAll('[data-sheet-variant]').forEach(function (button) {
            button.addEventListener('click', function () {
                const nextVariant = button.dataset.sheetVariant;
                if (state.config.sheet_variant === nextVariant) {
                    return;
                }
                state.config.sheet_variant = nextVariant;
                if (nextVariant === 'general') {
                    state.config.answer_columns = generalAutoFlowColumn;
                } else {
                    state.config.question_count = getNearestPresetQuestionCount(state.config.question_count);
                }
                state.config = normalizeConfig(state.config);
                applyStateToControls();
                markDirty();
                render();
            });
        });

        document.querySelectorAll('[data-question-count]').forEach(function (button) {
            button.addEventListener('click', function () {
                state.config.question_count = parseInt(button.dataset.questionCount, 10);
                state.config = normalizeConfig(state.config);
                applyStateToControls();
                markDirty();
                render();
            });
        });

        document.querySelectorAll('[data-answer-columns]').forEach(function (button) {
            button.addEventListener('click', function () {
                const columns = parseInt(button.dataset.answerColumns, 10);
                const maxQuestions = getGeneralColumnLimit(columns);
                if (state.config.question_count > maxQuestions) {
                    showToast(columns + ' columns support up to ' + maxQuestions + ' questions on General Normal OMR.', 'warning');
                    return;
                }
                state.config.answer_columns = columns;
                state.config = normalizeConfig(state.config);
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
        state.config = normalizeConfig(deepClone(defaultConfig));
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

    function normalizeConfig(rawConfig) {
        const next = rawConfig && typeof rawConfig === 'object' ? rawConfig : {};
        const config = deepClone(defaultConfig);

        config.template_type = defaultConfig.template_type;
        config.sheet_variant = next.sheet_variant === 'general' ? 'general' : 'institutional';
        config.question_count = parseInteger(next.question_count, defaultConfig.question_count);
        config.answer_columns = parseInteger(next.answer_columns, defaultConfig.answer_columns || 4);
        config.theme_color = next.theme_color || config.theme_color;
        config.bubble_size = next.bubble_size || config.bubble_size;
        config.header_mode = next.header_mode || config.header_mode;
        config.header = Object.assign({}, config.header, next.header || {});
        config.fields = Object.assign({}, config.fields, next.fields || {});
        config.instructions = Array.isArray(next.instructions) ? next.instructions.slice(0, 6) : config.instructions;

        if (config.sheet_variant === 'general') {
            config.question_count = clamp(
                config.question_count,
                generalRules.min_question_count,
                generalRules.max_question_count
            );
            config.answer_columns = getCompatibleGeneralColumns(config.question_count, config.answer_columns);
        } else {
            config.question_count = getNearestPresetQuestionCount(config.question_count);
            config.answer_columns = getInstitutionalLayout(config.question_count).answer_grid.columns;
        }

        return config;
    }

    function parseInteger(value, fallback) {
        const parsed = parseInt(value, 10);
        return Number.isInteger(parsed) ? parsed : fallback;
    }

    function clamp(value, min, max) {
        return Math.min(max, Math.max(min, value));
    }

    function getInstitutionalLayout(questionCount) {
        return layouts[String(questionCount)] || layouts[questionCount] || layouts[String(defaultConfig.question_count)] || layouts[defaultConfig.question_count];
    }

    function getNearestPresetQuestionCount(questionCount) {
        const presets = Object.keys(layouts)
            .map(function (key) { return parseInt(key, 10); })
            .filter(Number.isInteger)
            .sort(function (a, b) { return a - b; });
        if (!presets.length) {
            return questionCount;
        }
        return presets.reduce(function (closest, preset) {
            return Math.abs(preset - questionCount) < Math.abs(closest - questionCount) ? preset : closest;
        }, presets[0]);
    }

    function getGeneralColumnLimit(columns) {
        return parseInteger(generalRules.max_question_count_by_column[columns], generalRules.max_question_count);
    }

    function getMinimumCompatibleGeneralColumns(questionCount) {
        void questionCount;
        return generalAutoFlowColumn;
    }

    function getCompatibleGeneralColumns(questionCount, requestedColumns) {
        const supported = (generalRules.supported_columns || [1, 2, 3, 4]).map(function (value) {
            return parseInt(value, 10);
        });
        const fallback = supported.includes(generalAutoFlowColumn) ? generalAutoFlowColumn : supported[0];
        const desired = supported.includes(requestedColumns) ? requestedColumns : fallback;
        if (desired === generalAutoFlowColumn) {
            return generalAutoFlowColumn;
        }
        if (questionCount <= getGeneralColumnLimit(desired)) {
            return desired;
        }
        return fallback;
    }

    function getGeneralDistribution(questionCount, selectedColumns) {
        if (selectedColumns === generalAutoFlowColumn) {
            const columnQuestionCounts = [];
            let remaining = questionCount;
            while (remaining > 0) {
                const take = Math.min(remaining, generalMaxRowsPerAutoColumn);
                columnQuestionCounts.push(take);
                remaining -= take;
            }
            return {
                columns: columnQuestionCounts.length,
                rows: Math.max.apply(null, columnQuestionCounts),
                columnQuestionCounts: columnQuestionCounts,
            };
        }

        const base = Math.floor(questionCount / selectedColumns);
        const remainder = questionCount % selectedColumns;
        const columnQuestionCounts = [];
        for (let index = 0; index < selectedColumns; index += 1) {
            columnQuestionCounts.push(base + (index < remainder ? 1 : 0));
        }
        return {
            columns: selectedColumns,
            rows: Math.max.apply(null, columnQuestionCounts),
            columnQuestionCounts: columnQuestionCounts,
        };
    }

    function getResolvedLayout() {
        if (state.config.sheet_variant !== 'general') {
            return getInstitutionalLayout(state.config.question_count);
        }

        const distribution = getGeneralDistribution(state.config.question_count, state.config.answer_columns);
        const spec = generalColumnLayouts[distribution.columns] || generalColumnLayouts[4];
        const availableRowsHeight = 270 - 102 - spec.header_height_mm;
        const rowHeight = Math.min(spec.max_row_height_mm, availableRowsHeight / distribution.rows);
        return {
            page: { width_mm: 210, height_mm: 297 },
            answer_grid: {
                x_mm: spec.x_mm,
                y_mm: 102,
                columns: distribution.columns,
                rows: distribution.rows,
                column_width_mm: spec.column_width_mm,
                column_gap_mm: spec.column_gap_mm,
                row_height_mm: Number(rowHeight.toFixed(2)),
                header_height_mm: spec.header_height_mm,
                number_width_mm: spec.number_width_mm,
                column_question_counts: distribution.columnQuestionCounts,
            },
        };
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
        const previousAnswerColumns = state.config.answer_columns;
        if (state.config.sheet_variant === 'general') {
            const enteredCount = parseInt(els.omrCustomQuestionCount.value, 10);
            if (Number.isInteger(enteredCount)) {
                state.config.question_count = enteredCount;
            }
        }
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

        state.config = normalizeConfig(state.config);
        if (
            state.config.sheet_variant === 'general' &&
            previousAnswerColumns !== generalAutoFlowColumn &&
            previousAnswerColumns !== state.config.answer_columns &&
            state.config.answer_columns === generalAutoFlowColumn &&
            state.config.question_count > getGeneralColumnLimit(previousAnswerColumns)
        ) {
            showToast(
                previousAnswerColumns + ' columns support up to ' + getGeneralColumnLimit(previousAnswerColumns) + ' questions, so the layout switched to Auto flow.',
                'warning'
            );
        }
        if (els.omrCustomQuestionCount && state.config.sheet_variant === 'general') {
            els.omrCustomQuestionCount.value = state.config.question_count;
        }
        markDirty();
        render();
    }

    function applyStateToControls() {
        state.config = normalizeConfig(state.config);
        els.omrTemplateName.value = state.name || '';
        els.omrInstitutionInput.value = state.config.header.institution || '';
        els.omrTitleInput.value = state.config.header.title || '';
        els.omrSubtitleInput.value = state.config.header.subtitle || '';
        if (els.omrCustomQuestionCount) {
            els.omrCustomQuestionCount.value = state.config.question_count;
        }
        els.omrFieldRoll.checked = !!state.config.fields.roll;
        els.omrFieldSetCode.checked = !!state.config.fields.set_code;
        els.omrFieldSubjectCode.checked = !!state.config.fields.subject_code;

        els.instructions.forEach(function (input, index) {
            input.value = state.config.instructions[index] || '';
        });

        setActiveState('[data-sheet-variant]', 'sheetVariant', state.config.sheet_variant);
        setActiveState('[data-question-count]', 'questionCount', String(state.config.question_count));
        setActiveState('[data-answer-columns]', 'answerColumns', String(state.config.answer_columns));
        setActiveState('[data-bubble-size]', 'bubbleSize', state.config.bubble_size);
        setActiveState('[data-header-mode]', 'headerMode', state.config.header_mode);
        setActiveState('[data-theme-color]', 'themeColor', state.config.theme_color);

        const isGeneral = state.config.sheet_variant === 'general';
        if (els.omrPresetLayoutControls) {
            els.omrPresetLayoutControls.hidden = isGeneral;
        }
        if (els.omrGeneralLayoutControls) {
            els.omrGeneralLayoutControls.hidden = !isGeneral;
        }
        if (els.omrHeaderModeGroup) {
            els.omrHeaderModeGroup.hidden = isGeneral;
        }
        if (els.omrFieldsPanel) {
            els.omrFieldsPanel.hidden = isGeneral;
        }
        if (els.omrInstructionsPanel) {
            els.omrInstructionsPanel.hidden = isGeneral;
        }

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
            state.config = normalizeConfig(template.config_json);
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
            state.config = normalizeConfig(data.template.config_json);
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
        const layout = getResolvedLayout();
        renderPreview(layout);
        updateMeta();
        els.omrQuestionCountLabel.innerHTML = '<i class="bi bi-ui-checks-grid"></i> ' + state.config.question_count + ' questions';
        if (els.omrColumnCountLabel) {
            els.omrColumnCountLabel.innerHTML = '<i class="bi bi-columns-gap"></i> ' + getColumnCountLabel(layout.answer_grid.columns);
        }
        if (els.omrVariantLabel) {
            els.omrVariantLabel.innerHTML = state.config.sheet_variant === 'general'
                ? '<i class="bi bi-grid-1x2"></i> General normal'
                : '<i class="bi bi-grid-1x2"></i> Institutional preset';
        }
        if (els.omrScanStatusText) {
            els.omrScanStatusText.textContent = state.config.sheet_variant === 'general'
                ? getGeneralStatusText(layout.answer_grid.columns)
                : 'Preset geometry locked for reliable scanning.';
        }
    }

    function getColumnCountLabel(columnCount) {
        if (state.config.sheet_variant === 'general' && state.config.answer_columns === generalAutoFlowColumn) {
            return 'Auto flow · ' + columnCount + (columnCount === 1 ? ' column' : ' columns');
        }
        return columnCount + (columnCount === 1 ? ' column' : ' columns');
    }

    function getGeneralStatusText(renderColumns) {
        if (state.config.answer_columns === generalAutoFlowColumn) {
            return renderColumns === 1
                ? 'Auto flow keeps everything in the first column until more space is needed.'
                : 'Auto flow filled the first column first, then opened the next column.';
        }
        return 'Questions are balanced across your selected columns.';
    }

    function renderPreview(layout) {
        const theme = themes[state.config.theme_color] || { hex: '#f45d74' };
        const accentHex = theme.hex;
        const soft = hexToRgba(accentHex, 0.16);
        const lighter = hexToRgba(accentHex, 0.08);

        els.omrPreviewSheet.style.setProperty('--omr-accent', accentHex);
        els.omrPreviewSheet.style.setProperty('--omr-accent-soft', soft);
        els.omrPreviewSheet.style.setProperty('--omr-accent-light', lighter);

        const blocks = [];
        blocks.push(renderMarkers());
        blocks.push(state.config.sheet_variant === 'general' ? renderGeneralHeaderFixed() : renderHeaderFixed());
        blocks.push(state.config.sheet_variant === 'general' ? renderGeneralIdentitySectionFixed() : renderIdentitySectionFixed());
        blocks.push(renderAnswersFixed(layout));
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

    function renderGeneralHeader() {
        const subtitle = state.config.header.subtitle
            ? '<p>' + escapeHtml(state.config.header.subtitle) + '</p>'
            : '';
        const institution = state.config.header.institution
            ? '<p>' + escapeHtml(state.config.header.institution) + '</p>'
            : '';
        return '<div class="omr-preview-general-header" style="' + boxStyle(18, 12, 174, 20) + '">' +
            '<h2>' + escapeHtml(state.config.header.title || 'সাধারণ OMR উত্তরপত্র') + '</h2>' +
            subtitle +
            institution +
            '<div class="omr-preview-general-divider"></div>' +
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

    function renderGeneralIdentitySection() {
        const rows = [
            ['নাম'],
            ['শ্রেণি', 'সেকশন'],
            ['বিষয়', 'রোল'],
        ];
        let html = '<div class="omr-preview-general-form" style="' + boxStyle(18, 40, 174, 28) + '">';
        rows.forEach(function (row) {
            html += '<div class="omr-preview-general-row">';
            row.forEach(function (label) {
                html += '<div class="omr-preview-general-field"><strong>' + escapeHtml(label) + ':</strong><span></span></div>';
            });
            html += '</div>';
        });
        html += '</div>';
        return html;
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

        if (state.config.sheet_variant === 'general') {
            html = '<div class="omr-preview-answer-title" style="' + titleStyle + '">সাধারণ বহুনির্বাচনি উত্তরপত্র</div>';
        }

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

    function renderHeaderFixed() {
        if (state.config.header_mode === 'manual') {
            return '<div class="omr-preview-header omr-preview-header-manual" style="' + boxStyle(14, 10, 182, 30) + '">' +
                '<div class="omr-preview-line"><strong>' + omrCopy.institution + '</strong><span></span></div>' +
                '<div class="omr-preview-line"><strong>' + omrCopy.examName + '</strong><span></span></div>' +
                '<div class="omr-preview-line"><strong>' + omrCopy.subtitle + '</strong><span></span></div>' +
                '</div>';
        }

        const copy = [];
        if (state.config.header.title) {
            copy.push('<h2>' + escapeHtml(state.config.header.title) + '</h2>');
        }
        if (state.config.header.subtitle) {
            copy.push('<p class="omr-preview-subtitle">' + escapeHtml(state.config.header.subtitle) + '</p>');
        }
        if (state.config.header.institution) {
            copy.push('<p class="omr-preview-institution">' + escapeHtml(state.config.header.institution) + '</p>');
        }

        return '<div class="omr-preview-header" style="' + boxStyle(14, 10, 182, 30) + '">' +
            '<p class="omr-preview-warning">' + omrCopy.warning + '</p>' +
            '<div class="omr-preview-header-copy">' + copy.join('') + '</div>' +
            '</div>';
    }

    function renderGeneralHeaderFixed() {
        const parts = [];
        if (state.config.header.title) {
            parts.push('<h2>' + escapeHtml(state.config.header.title) + '</h2>');
        }
        if (state.config.header.subtitle) {
            parts.push('<p>' + escapeHtml(state.config.header.subtitle) + '</p>');
        }
        if (state.config.header.institution) {
            parts.push('<p>' + escapeHtml(state.config.header.institution) + '</p>');
        }
        return '<div class="omr-preview-general-header" style="' + boxStyle(18, 12, 174, 20) + '">' +
            parts.join('') +
            '<div class="omr-preview-general-divider"></div>' +
            '</div>';
    }

    function renderIdentitySectionFixed() {
        const html = [];
        if (state.config.fields.roll) {
            html.push(renderMatrixBlock({
                title: omrCopy.rollNumber,
                x: 14,
                y: 52,
                w: 42,
                h: 82,
                cols: 6,
                labels: digitLabels,
            }));
        }
        if (state.config.fields.subject_code) {
            html.push(renderMatrixBlock({
                title: omrCopy.subjectCode,
                x: 59,
                y: 52,
                w: 38,
                h: 82,
                cols: 3,
                labels: digitLabels,
            }));
        }
        if (state.config.fields.set_code) {
            html.push(renderMatrixBlock({
                title: omrCopy.setCode,
                x: 100,
                y: 52,
                w: 20,
                h: 82,
                cols: 1,
                labels: optionLabels,
            }));
        }

        html.push('<div class="omr-preview-instructions" style="' + boxStyle(125, 52, 70, 40) + '">' +
            '<div class="omr-preview-card-title">' + omrCopy.instructions + '</div>' +
            '<ol>' + state.config.instructions.slice(0, 6).map(function (instruction) {
                return '<li>' + escapeHtml(instruction) + '</li>';
            }).join('') + '</ol></div>');
        html.push('<div class="omr-preview-signature" style="' + boxStyle(125, 97, 46, 23) + '">' + omrCopy.signature + '</div>');
        return html.join('');
    }

    function renderGeneralIdentitySectionFixed() {
        const rows = [
            [omrCopy.name],
            [omrCopy.className, omrCopy.section],
            [omrCopy.subject, omrCopy.roll],
        ];
        let html = '<div class="omr-preview-general-form" style="' + boxStyle(18, 40, 174, 28) + '">';
        rows.forEach(function (row) {
            html += '<div class="omr-preview-general-row">';
            row.forEach(function (label) {
                html += '<div class="omr-preview-general-field"><strong>' + escapeHtml(label) + ':</strong><span></span></div>';
            });
            html += '</div>';
        });
        html += '</div>';
        return html;
    }

    function renderAnswersFixed(layout) {
        if (state.config.sheet_variant === 'general') {
            return renderGeneralAnswersFixed(layout);
        }

        const grid = layout.answer_grid;
        const titleStyle = boxStyle(40, grid.y_mm - 13, 130, 8);
        let html = '<div class="omr-preview-answer-title" style="' + titleStyle + '">' + omrCopy.institutionalAnswerTitle + '</div>';

        for (let columnIndex = 0; columnIndex < grid.columns; columnIndex += 1) {
            const x = grid.x_mm + (columnIndex * (grid.column_width_mm + grid.column_gap_mm));
            const y = grid.y_mm;
            const height = grid.header_height_mm + (grid.rows * grid.row_height_mm);
            const headerPct = percent(grid.header_height_mm, height);
            const rowsPct = (100 - parseFloat(headerPct)).toFixed(4);
            const startNumber = (columnIndex * grid.rows) + 1;
            const endNumber = startNumber + grid.rows - 1;
            html += '<div class="omr-preview-answer-column" style="' + boxStyle(x, y, grid.column_width_mm, height) + '">' +
                '<div class="omr-preview-answer-header" style="height:' + headerPct + '%">' +
                '<span class="question-label" style="width:' + percent(grid.number_width_mm, grid.column_width_mm) + '%">' + omrCopy.question + '</span>' +
                '<span class="answer-label" style="flex:1 1 0">' + omrCopy.answer + '</span>' +
                '</div>' +
                '<div class="omr-preview-answer-rows" style="height:' + rowsPct + '%">';

            for (let rowIndex = 0; rowIndex < grid.rows; rowIndex += 1) {
                const number = startNumber + rowIndex;
                html += '<div class="omr-preview-answer-row">' +
                    '<span class="omr-preview-qnum" style="width:' + percent(grid.number_width_mm, grid.column_width_mm) + '%">' + toBanglaNumber(number) + '</span>' +
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

    function renderGeneralAnswersFixed(layout) {
        const grid = layout.answer_grid;
        const columnQuestionCounts = grid.column_question_counts || new Array(grid.columns).fill(grid.rows);
        const titleStyle = boxStyle(40, grid.y_mm - 13, 130, 8);
        const frame = getGeneralAnswerFrameMetrics(grid);
        let html = '<div class="omr-preview-answer-title" style="' + titleStyle + '">' + omrCopy.generalAnswerTitle + '</div>';
        let nextNumber = 1;

        html += '<div class="omr-preview-answer-frame omr-preview-answer-frame-general" style="' +
            boxStyle(frame.x_mm, frame.y_mm, frame.width_mm, frame.height_mm) + '"></div>';

        getGeneralAnswerMarkerSpecs(frame).forEach(function (marker) {
            html += '<div class="omr-preview-answer-marker" style="' +
                boxStyle(marker.x_mm, marker.y_mm, marker.width_mm, marker.height_mm) + '"></div>';
        });

        for (let columnIndex = 0; columnIndex < grid.columns; columnIndex += 1) {
            const actualRows = parseInt(columnQuestionCounts[columnIndex], 10) || 0;
            if (!actualRows) {
                continue;
            }
            const x = grid.x_mm + (columnIndex * (grid.column_width_mm + grid.column_gap_mm));
            const y = grid.y_mm + generalAnswerMarkerBandHeightMm;
            const height = actualRows * grid.row_height_mm;
            html += '<div class="omr-preview-answer-column omr-preview-answer-column-general" style="' +
                boxStyle(x, y, grid.column_width_mm, height) + '">' +
                '<div class="omr-preview-answer-rows" style="height:100%">';

            for (let rowIndex = 0; rowIndex < actualRows; rowIndex += 1) {
                const number = nextNumber + rowIndex;
                html += '<div class="omr-preview-answer-row">' +
                    '<span class="omr-preview-qnum" style="width:' + percent(grid.number_width_mm, grid.column_width_mm) + '%">' + toBanglaNumber(number) + '</span>' +
                    '<div class="omr-preview-options">';
                optionLabels.forEach(function (label) {
                    html += '<span class="omr-preview-option"><span class="omr-mini-bubble ' + state.config.bubble_size + '">' + label + '</span></span>';
                });
                html += '</div></div>';
            }

            html += '</div></div>';
            nextNumber += actualRows;
        }
        return html;
    }

    function getGeneralAnswerFrameMetrics(grid) {
        const width = (grid.columns * grid.column_width_mm) + ((grid.columns - 1) * grid.column_gap_mm);
        return {
            x_mm: grid.x_mm,
            y_mm: grid.y_mm,
            width_mm: width,
            height_mm: generalAnswerMarkerBandHeightMm + (grid.rows * grid.row_height_mm),
        };
    }

    function getGeneralAnswerMarkerSpecs(frame) {
        const markerWidth = 2.8;
        const markerHeight = 2.8;
        const topY = frame.y_mm + 1.1;
        const offsets = [
            2.1,
            frame.width_mm * 0.23,
            frame.width_mm * 0.29,
            frame.width_mm * 0.49,
            frame.width_mm - 10.2,
            frame.width_mm - 5.0,
        ];
        return offsets.map(function (offset) {
            return {
                x_mm: frame.x_mm + offset,
                y_mm: topY,
                width_mm: markerWidth,
                height_mm: markerHeight,
            };
        });
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
