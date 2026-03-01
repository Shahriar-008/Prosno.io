# Plan: Short Question & Creative Question Feature

**TL;DR** — Add two new question types (Short Question / সংক্ষিপ্ত প্রশ্ন and Creative Question / সৃজনশীল প্রশ্ন) as separate database tables (`ShortQuestion`, `CQQuestion`) with full admin CRUD, paper generation UI, and DOCX rendering. Both types use soft-delete, get their own admin nav group "প্রশ্ন ব্যবস্থাপনা", filter by subject/chapter with cascading dropdowns, and render in the DOCX using the same 2-column layout with Bengali section headers (খ-বিভাগ, গ-বিভাগ).

**Steps**

## 1. New Model Classes — [app/models.py](app/models.py)

Add two new classes after the existing `Question` model (around line 185):

- **`ShortQuestion`** — table `short_questions`. Fields: `id` (PK), `subject_id` (FK → subjects, required), `chapter_id` (FK → chapters, nullable), `question_text` (Text, required), `marks` (Integer, default 2), `is_active` (Boolean, default True), `created_at` (DateTime, default utcnow), `created_by` (FK → users). Add a `to_dict()` method returning `{id, question_text, marks, type: 'short'}`. Add relationship from `Subject` and `Chapter` (backref `short_questions`, lazy `dynamic`).

- **`CQQuestion`** — table `cq_questions`. Fields: `id` (PK), `subject_id` (FK → subjects, required), `chapter_id` (FK → chapters, nullable), `stem` (Text, required — the উদ্দীপক), `part_ka` (Text — ক sub-question), `part_kha` (Text — খ), `part_ga` (Text — গ), `part_gha` (Text — ঘ), `marks_ka` (Integer, default 1), `marks_kha` (Integer, default 2), `marks_ga` (Integer, default 3), `marks_gha` (Integer, default 4), `is_active` (Boolean, default True), `created_at` (DateTime, default utcnow), `created_by` (FK → users). Add `to_dict()` returning all fields + `type: 'creative'`. Add `total_marks` property computing sum of 4 part marks.

## 2. Migration Tuples — [app/__init__.py](app/__init__.py#L284)

Tables are created automatically by `db.create_all()` (already called in the factory). No `ALTER TABLE` migration tuples needed for brand-new tables — SQLAlchemy's `create_all()` handles that. However, if any columns are later added to existing tables, add them to the migrations list.

Confirm `db.create_all()` is called inside `create_app()` to create the new tables on startup.

## 3. Admin Route Handlers — [app/routes/admin.py](app/routes/admin.py)

Add imports for `ShortQuestion`, `CQQuestion`, `Subject` at the top.

Add **8 new route handlers** following the existing CRUD pattern (modeled after the Question CRUD block):

**Short Questions:**
- `GET /admin/short-questions` → `short_questions()` — paginated list, filter by `subject` and `chapter` (query params). Query `ShortQuestion.query.filter_by(is_active=True)`, paginate per_page=20. Pass `subjects` list for filter dropdown.
- `GET,POST /admin/short-questions/new` → `add_short_question()` — form with fields: `subject_id` (select), `chapter_id` (select, cascading via existing `/api/chapters/<subject_id>` endpoint), `question_text` (textarea), `marks` (number input, default 2). On POST: create `ShortQuestion`, `log_activity('create', 'short_question', ...)`, flash, redirect.
- `GET,POST /admin/short-questions/<id>/edit` → `edit_short_question(id)` — `get_or_404`, pre-fill form, update on POST.
- `POST /admin/short-questions/<id>/delete` → `delete_short_question(id)` — `@admin_required`, set `is_active = False`, `log_activity('delete', 'short_question', ...)`.

**CQ Questions:**
- `GET /admin/cq-questions` → `cq_questions()` — same pattern, filter by subject/chapter.
- `GET,POST /admin/cq-questions/new` → `add_cq_question()` — form with: `subject_id`, `chapter_id`, `stem` (textarea), `part_ka/kha/ga/gha` (4 textareas), `marks_ka/kha/ga/gha` (4 number inputs). On POST: create `CQQuestion`, log activity.
- `GET,POST /admin/cq-questions/<id>/edit` → `edit_cq_question(id)`.
- `POST /admin/cq-questions/<id>/delete` → `delete_cq_question(id)` — `@admin_required`, soft-delete.

## 4. API Routes — [app/routes/api.py](app/routes/api.py)

Add two new endpoints for counting available questions (used by generate form validation):

- `GET /api/short-questions/count?subject_id=X&chapter_id=Y` → returns `{count: N}` of active ShortQuestions matching filters.
- `GET /api/cq-questions/count?subject_id=X&chapter_id=Y` → returns `{count: N}` of active CQQuestions matching filters.

Both `@csrf.exempt`, read-only.

## 5. Admin Templates — 4 new files

**[templates/admin/short_questions.html](app/templates/admin/short_questions.html)** — extends `admin/base.html`. Subject/chapter filter dropdowns at top. Table columns: #, Question Text (truncated 80 chars), Subject, Chapter, Marks, Status (badge), Actions (Edit/Delete). Pagination via `iter_pages()`.

**[templates/admin/short_question_form.html](app/templates/admin/short_question_form.html)** — extends `admin/base.html`. Card layout with: Subject dropdown (required), Chapter dropdown (cascading JS using `/api/chapters/<subject_id>`), Question Text (textarea, Bengali placeholder), Marks (number, default 2). Submit button: "সংরক্ষণ করুন". Pre-fill when editing.

**[templates/admin/cq_questions.html](app/templates/admin/cq_questions.html)** — same pattern as short_questions list. Table columns: #, Stem (truncated 80 chars), Parts preview (ক–ঘ icons), Subject, Chapter, Total Marks, Status, Actions.

**[templates/admin/cq_question_form.html](app/templates/admin/cq_question_form.html)** — extends `admin/base.html`. Card layout with: Subject/Chapter dropdowns, Stem textarea (label: "উদ্দীপক"), 4 sub-part rows each with textarea + marks input (inline):
  - ক — `part_ka` / `marks_ka` (default 1)
  - খ — `part_kha` / `marks_kha` (default 2)
  - গ — `part_ga` / `marks_ga` (default 3)
  - ঘ — `part_gha` / `marks_gha` (default 4)

  Running total shown below via JS (`marks_ka + marks_kha + marks_ga + marks_gha`). Warning badge (yellow) if total ≠ 10 — "মোট নম্বর ১০ হওয়া উচিত" — but does **not** block save.

## 6. Admin Sidebar — [templates/admin/base.html](app/templates/admin/base.html#L75)

Insert a new nav group after the existing "Content Management" items (after the Questions link, around line 75):

```html
<li class="nav-header">প্রশ্ন ব্যবস্থাপনা</li>
<li class="nav-item">
    <a href="{{ url_for('admin.short_questions') }}" class="nav-link {% if 'short_question' in request.endpoint %}active{% endif %}">
        <i class="bi bi-card-text"></i>
        <span>সংক্ষিপ্ত প্রশ্ন</span>
    </a>
</li>
<li class="nav-item">
    <a href="{{ url_for('admin.cq_questions') }}" class="nav-link {% if 'cq_question' in request.endpoint %}active{% endif %}">
        <i class="bi bi-journal-text"></i>
        <span>সৃজনশীল প্রশ্ন</span>
    </a>
</li>
```

Active state detection: `'short_question' in request.endpoint` and `'cq_question' in request.endpoint`.

## 7. Generate Page UI — [templates/main/generate.html](app/templates/main/generate.html)

Add a collapsible Bootstrap accordion section titled **"অতিরিক্ত প্রশ্ন বিভাগ"** after the existing MCQ options but before the Generate button.

Two sub-panels inside:

**Panel 1: সংক্ষিপ্ত প্রশ্ন (Short Questions)**
- Checkbox: `sq_include` — "সংক্ষিপ্ত প্রশ্ন যোগ করুন"
- When checked, reveal:
  - `sq_subject_id` select (populated from `/api/subjects/<class_id>` — same class already selected)
  - `sq_chapter_id` select (cascading from subject, optional)
  - `sq_include_count` (M) — number input, label: "মোট প্রশ্ন সংখ্যা"
  - `sq_answer_count` (N) — number input, label: "উত্তর দিতে হবে"
  - `sq_marks` — marks per question (default 2)
- JS validation: N ≥ 1, N ≤ M, M ≤ available count (fetched from `/api/short-questions/count`). Inline error messages in Bengali.

**Panel 2: সৃজনশীল প্রশ্ন (Creative Questions)**
- Same checkbox/reveal pattern with `cq_include`, `cq_subject_id`, `cq_chapter_id`, `cq_include_count`, `cq_answer_count`.
- JS validation: same rules. Available count from `/api/cq-questions/count`.

## 8. Main Route Handler — [app/routes/main.py](app/routes/main.py#L152)

Modify the `/generate-paper` POST handler:

- Extract new fields from JSON: `sq_include`, `sq_subject_id`, `sq_chapter_id`, `sq_include_count`, `sq_answer_count`, `sq_marks`, `cq_include`, `cq_subject_id`, `cq_chapter_id`, `cq_include_count`, `cq_answer_count`.
- **Server-side validation**: if `sq_include` is true, validate N ≤ M, M ≤ available active ShortQuestions (filtered by subject/chapter). Same for CQ.
- Query and randomly sample: `ShortQuestion.query.filter(...)`.`order_by(db.func.random()).limit(M)` for SQ; same for CQ.
- Build config dicts:
  ```python
  sq_config = {'questions': [...], 'answer_count': N, 'marks_per_question': marks}
  cq_config = {'questions': [...], 'answer_count': N}
  ```
- Pass `sq_config` and `cq_config` to `generate_paper_from_db()` and `generate_paper_to_memory()`.
- Update `paper_config['marks']` to include SQ and CQ marks in the total.
- Store SQ/CQ question IDs in `GeneratedPaper` (extend `custom_paper_config` JSON field to hold `sq_question_ids` and `cq_question_ids` for paper snapshot).

## 9. Document Generator — [app/utils/document_generator.py](app/utils/document_generator.py)

### 9a. New helper function: `add_short_question_section(document, sq_config)`

- If `sq_config` is None or `sq_config['questions']` is empty, return immediately (skip section).
- Add section header paragraph: **"খ-বিভাগ (সংক্ষিপ্ত প্রশ্ন)"** — bold, centered, `Pt(10)`.
- Add instruction paragraph: `"নিচের যেকোনো {N}টির উত্তর দাও। প্রতিটি প্রশ্নের মান {marks}।"` — using `to_bengali_numeral()`.
- Iterate questions with Bengali numbering (`১।`, `২।`, etc.):
  - Left: `{bengali_num}। {question_text}`
  - Right-aligned on same line: `{marks}` in Bengali
- Use math-aware text rendering (reuse existing `_has_math_expression` / OMML logic if text contains math).

### 9b. New helper function: `add_cq_section(document, cq_config)`

- If `cq_config` is None or empty, skip.
- Header: **"গ-বিভাগ (সৃজনশীল প্রশ্ন)"** — bold, centered.
- Instruction: `"নিচের যেকোনো {N}টির উত্তর দাও।"`
- For each CQ question:
  - `{bengali_num}। উদ্দীপক:` followed by stem text — optionally with a light gray shading on the stem paragraph (using `w:shd` XML element).
  - Sub-parts indented (left indent ~0.5 inch), each on its own line:
    - `ক. {part_ka}` with right-aligned `{marks_ka}` in Bengali
    - `খ. {part_kha}` …
    - `গ. {part_ga}` …
    - `ঘ. {part_gha}` …

### 9c. Modify `create_question_paper()`

- Add `sq_config=None` and `cq_config=None` parameters.
- After rendering MCQ questions (the existing for-loop), call:
  1. `add_short_question_section(document, sq_config)` — renders খ-বিভাগ
  2. `add_cq_section(document, cq_config)` — renders গ-বিভাগ
- Update total marks calculation to include SQ and CQ marks.

### 9d. Modify `generate_paper_from_db()` and `generate_paper_to_memory()`

Propagate `sq_config` and `cq_config` kwargs through to `create_question_paper()`. Convert ShortQuestion/CQQuestion model objects to dicts via their `to_dict()` methods before passing.

## 10. Update Existing MCQ Section Header

Currently MCQ questions have no section label. Add **"ক-বিভাগ (বহুনির্বাচনী প্রশ্ন)"** as a heading before the MCQ question loop in `create_question_paper()`, but **only** if SQ or CQ sections are also present (to avoid changing existing MCQ-only papers).

---

## Verification

1. Run `python run.py` — confirm both new tables (`short_questions`, `cq_questions`) are created automatically by `db.create_all()`.
2. Navigate to `/admin/short-questions` and `/admin/cq-questions` — verify empty list renders, add/edit/delete works.
3. Add sample short questions and CQ questions via admin forms, verify activity log entries.
4. On `/generate` page, select a class/subject, expand "অতিরিক্ত প্রশ্ন বিভাগ", enable SQ checkbox, set M=3 N=2, generate → verify DOCX contains খ-বিভাগ section with 3 questions and "যেকোনো ২টির" instruction.
5. Same for CQ — verify গ-বিভাগ section with stem shading, indented sub-parts, right-aligned marks.
6. Test validation: set N > M → verify inline error appears, form doesn't submit. Set M > available count → same.
7. Verify soft-delete: delete a short question from admin → confirm `is_active=False` but row still exists in DB.
8. Open teacher copy DOCX — verify same layout (no answer key differences since SQ/CQ don't have correct answers).

---

## Decisions

- **Separate tables** chosen over extending `Question` model — cleaner separation, avoids nullable `answer_options` issue
- **2-column layout** kept for SQ/CQ sections — per user preference
- **Soft-delete** via `is_active=False` — diverges from existing hard-delete pattern on MCQ questions but matches user's request
- **New sidebar nav group** "প্রশ্ন ব্যবস্থাপনা" — distinct from Content Management
- **CQ marks total ≠ 10** shows warning but doesn't block save — per user spec
- **MCQ section header** (ক-বিভাগ) only added when SQ/CQ sections are also present — avoids breaking existing MCQ-only papers
- **M** (include count) and **N** (answer count) are per-section, not global
- **Questions randomly sampled** at generation time, not stored; only the final paper snapshot (question IDs) saved in `GeneratedPaper`
