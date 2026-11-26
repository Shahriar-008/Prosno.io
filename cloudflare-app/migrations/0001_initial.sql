-- Prosno.io Cloudflare D1 Initial Schema (0001_initial.sql)
-- Maps all 23 SQLAlchemy models + native Workers sessions + FTS5 search

PRAGMA foreign_keys = ON;

-- 1. Users & Native Auth Sessions
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  public_uid TEXT NOT NULL UNIQUE,
  username TEXT NOT NULL UNIQUE,
  email TEXT NOT NULL UNIQUE,
  display_name TEXT,
  password_hash TEXT NOT NULL,
  auth_provider TEXT NOT NULL DEFAULT 'local', -- local | google
  google_sub TEXT UNIQUE,
  role TEXT NOT NULL DEFAULT 'teacher',        -- admin | editor | teacher
  is_admin INTEGER NOT NULL DEFAULT 0,
  is_active_user INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  created_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
  last_login TEXT
);

CREATE INDEX IF NOT EXISTS idx_users_public_uid ON users(public_uid);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);

-- 2. Core Curriculum Hierarchy
CREATE TABLE IF NOT EXISTS classes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  name_bn TEXT,
  level TEXT,
  "order" INTEGER NOT NULL DEFAULT 0,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS subjects (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  name_bn TEXT,
  code TEXT,
  class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
  "order" INTEGER NOT NULL DEFAULT 0,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  created_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_subjects_class_id ON subjects(class_id);

CREATE TABLE IF NOT EXISTS chapters (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  name_bn TEXT,
  chapter_number INTEGER,
  subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
  "order" INTEGER NOT NULL DEFAULT 0,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  created_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_chapters_subject_id ON chapters(subject_id);

-- 3. Questions (MCQ, Short Question, Creative Question)
CREATE TABLE IF NOT EXISTS questions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  question_text TEXT NOT NULL,
  question_type TEXT NOT NULL DEFAULT 'simple', -- simple | complex
  sub_options TEXT,                             -- JSON array
  final_prompt TEXT,
  answer_options TEXT NOT NULL,                 -- JSON array of 4 options
  correct_answer TEXT NOT NULL,
  explanation TEXT,
  board TEXT,
  year INTEGER,
  chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
  difficulty TEXT NOT NULL DEFAULT 'medium',
  marks INTEGER NOT NULL DEFAULT 1,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  created_by INTEGER REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_questions_chapter_id ON questions(chapter_id);

CREATE TABLE IF NOT EXISTS short_questions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
  chapter_id INTEGER REFERENCES chapters(id) ON DELETE SET NULL,
  question_text TEXT NOT NULL,
  answer TEXT,
  marks INTEGER NOT NULL DEFAULT 2,
  board TEXT,
  year INTEGER,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  created_by INTEGER REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_short_questions_subject_id ON short_questions(subject_id);
CREATE INDEX IF NOT EXISTS idx_short_questions_chapter_id ON short_questions(chapter_id);

CREATE TABLE IF NOT EXISTS cq_questions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
  chapter_id INTEGER REFERENCES chapters(id) ON DELETE SET NULL,
  stem TEXT NOT NULL,
  part_ka TEXT,
  part_kha TEXT,
  part_ga TEXT,
  part_gha TEXT,
  marks_ka INTEGER NOT NULL DEFAULT 1,
  marks_kha INTEGER NOT NULL DEFAULT 2,
  marks_ga INTEGER NOT NULL DEFAULT 3,
  marks_gha INTEGER NOT NULL DEFAULT 4,
  board TEXT,
  year INTEGER,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  created_by INTEGER REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_cq_questions_subject_id ON cq_questions(subject_id);
CREATE INDEX IF NOT EXISTS idx_cq_questions_chapter_id ON cq_questions(chapter_id);

-- 4. Generated Papers, Question Sets, OMR Templates, Generation Logs
CREATE TABLE IF NOT EXISTS generated_papers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT,                                 -- public_uid of creator (null for guest)
  title TEXT,
  class_id INTEGER REFERENCES classes(id) ON DELETE SET NULL,
  subject_id INTEGER REFERENCES subjects(id) ON DELETE SET NULL,
  chapter_ids TEXT,                             -- JSON array
  question_ids TEXT,                            -- JSON array
  question_count INTEGER,
  time_minutes INTEGER,
  file_path TEXT,
  file_path_answers TEXT,
  custom_questions_json TEXT,                   -- JSON array for custom/guest papers
  custom_paper_config TEXT,                     -- JSON object (sq_config, cq_config, studio, marks)
  omr_style INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  download_count INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_generated_papers_user_id ON generated_papers(user_id);

CREATE TABLE IF NOT EXISTS question_sets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  name TEXT NOT NULL,
  questions_json TEXT NOT NULL,                 -- JSON array
  paper_config TEXT,                            -- JSON object
  source TEXT NOT NULL DEFAULT 'custom',        -- db | custom | builder
  paper_id INTEGER REFERENCES generated_papers(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  share_token TEXT UNIQUE,
  is_shared INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_question_sets_user_id ON question_sets(user_id);
CREATE INDEX IF NOT EXISTS idx_question_sets_share_token ON question_sets(share_token);

CREATE TABLE IF NOT EXISTS omr_templates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  name TEXT NOT NULL,
  config_json TEXT NOT NULL,                    -- JSON object
  question_count INTEGER NOT NULL,
  download_count INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_omr_templates_user_id ON omr_templates(user_id);

CREATE TABLE IF NOT EXISTS generation_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  generation_type TEXT NOT NULL DEFAULT 'db',
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_generation_logs_user_id ON generation_logs(user_id);

-- 5. AI Generator Config & Logs + Admin Activity Logs
CREATE TABLE IF NOT EXISTS ai_generator_config (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  api_key TEXT,
  api_provider TEXT NOT NULL DEFAULT 'gemini',
  model_name TEXT NOT NULL DEFAULT 'gemini-2.0-flash',
  prompt_template TEXT,
  questions_per_request INTEGER NOT NULL DEFAULT 5,
  interval_minutes INTEGER NOT NULL DEFAULT 5,
  max_requests_per_hour INTEGER NOT NULL DEFAULT 20,
  requests_this_hour INTEGER NOT NULL DEFAULT 0,
  hour_started TEXT,
  is_running INTEGER NOT NULL DEFAULT 0,
  current_class_id INTEGER REFERENCES classes(id) ON DELETE SET NULL,
  current_subject_id INTEGER REFERENCES subjects(id) ON DELETE SET NULL,
  current_chapter_id INTEGER REFERENCES chapters(id) ON DELETE SET NULL,
  started_at TEXT,
  last_run_at TEXT,
  total_questions_generated INTEGER NOT NULL DEFAULT 0,
  total_duplicates_skipped INTEGER NOT NULL DEFAULT 0,
  total_errors INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS ai_generator_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  class_id INTEGER REFERENCES classes(id) ON DELETE SET NULL,
  subject_id INTEGER REFERENCES subjects(id) ON DELETE SET NULL,
  chapter_id INTEGER REFERENCES chapters(id) ON DELETE SET NULL,
  status TEXT,
  questions_generated INTEGER NOT NULL DEFAULT 0,
  duplicates_found INTEGER NOT NULL DEFAULT 0,
  error_message TEXT,
  tokens_used INTEGER NOT NULL DEFAULT 0,
  api_response_time REAL,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS activity_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  action TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id INTEGER,
  entity_name TEXT,
  details TEXT,                                 -- JSON object
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- 6. Live Classroom Quiz System
CREATE TABLE IF NOT EXISTS quizzes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  join_code TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  question_set_id INTEGER REFERENCES question_sets(id) ON DELETE SET NULL,
  teacher_user_id TEXT NOT NULL,
  questions_json TEXT NOT NULL,                 -- JSON array
  time_limit_minutes INTEGER NOT NULL DEFAULT 30,
  shuffle_questions INTEGER NOT NULL DEFAULT 1,
  shuffle_options INTEGER NOT NULL DEFAULT 1,
  show_results_to_students INTEGER NOT NULL DEFAULT 1,
  status TEXT NOT NULL DEFAULT 'waiting',       -- waiting | active | ended
  started_at TEXT,
  ended_at TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_quizzes_join_code ON quizzes(join_code);
CREATE INDEX IF NOT EXISTS idx_quizzes_teacher_user_id ON quizzes(teacher_user_id);

CREATE TABLE IF NOT EXISTS quiz_sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  quiz_id INTEGER NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
  student_name TEXT NOT NULL,
  session_token TEXT NOT NULL UNIQUE,
  score INTEGER NOT NULL DEFAULT 0,
  total_questions INTEGER NOT NULL DEFAULT 0,
  responses_json TEXT,                          -- JSON object {"0": "selected_answer", ...}
  time_taken_seconds INTEGER,
  status TEXT NOT NULL DEFAULT 'joined',        -- joined | in_progress | submitted
  joined_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  submitted_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_quiz_sessions_quiz_id ON quiz_sessions(quiz_id);
CREATE INDEX IF NOT EXISTS idx_quiz_sessions_token ON quiz_sessions(session_token);

-- 7. Teacher Community Question Bank & Moderation
CREATE TABLE IF NOT EXISTS teacher_profiles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL UNIQUE,
  display_name TEXT,
  institute_name TEXT,
  institute_subtitle TEXT,
  logo_url TEXT,
  watermark_text TEXT,
  default_font TEXT DEFAULT 'hind',
  is_trusted INTEGER NOT NULL DEFAULT 0,
  trust_granted_at TEXT,
  trust_granted_by TEXT,
  approved_questions_count INTEGER NOT NULL DEFAULT 0,
  reputation_score INTEGER NOT NULL DEFAULT 0,
  account_created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  questions_created INTEGER NOT NULL DEFAULT 0,
  questions_published INTEGER NOT NULL DEFAULT 0,
  questions_used INTEGER NOT NULL DEFAULT 0,
  total_downloads INTEGER NOT NULL DEFAULT 0,
  average_rating REAL NOT NULL DEFAULT 0.0,
  contributor_rank TEXT NOT NULL DEFAULT 'Newcomer',
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_teacher_profiles_user_id ON teacher_profiles(user_id);

CREATE TABLE IF NOT EXISTS bank_questions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  teacher_id TEXT NOT NULL,
  class_id INTEGER REFERENCES classes(id) ON DELETE SET NULL,
  subject_id INTEGER REFERENCES subjects(id) ON DELETE SET NULL,
  chapter_id INTEGER REFERENCES chapters(id) ON DELETE SET NULL,
  question_type TEXT NOT NULL,                  -- MCQ | SQ | CQ
  question_text TEXT NOT NULL,
  answer TEXT,
  explanation TEXT,
  answer_options TEXT,                          -- JSON array
  correct_answer TEXT,
  stem TEXT,
  part_ka TEXT,
  part_kha TEXT,
  part_ga TEXT,
  part_gha TEXT,
  marks_ka INTEGER,
  marks_kha INTEGER,
  marks_ga INTEGER,
  marks_gha INTEGER,
  topic TEXT,
  difficulty TEXT NOT NULL DEFAULT 'medium',
  marks INTEGER NOT NULL DEFAULT 1,
  board TEXT,
  year INTEGER,
  visibility TEXT NOT NULL DEFAULT 'private',   -- private | pending | public | rejected
  status TEXT NOT NULL DEFAULT 'draft',         -- draft | submitted | approved | rejected
  published_at TEXT,
  rejected_at TEXT,
  rejection_reason TEXT,
  origin TEXT NOT NULL DEFAULT 'manual',        -- manual | ai_generated | copied
  source_question_id INTEGER REFERENCES bank_questions(id) ON DELETE SET NULL,
  usage_count INTEGER NOT NULL DEFAULT 0,
  download_count INTEGER NOT NULL DEFAULT 0,
  rating_total INTEGER NOT NULL DEFAULT 0,
  rating_count INTEGER NOT NULL DEFAULT 0,
  text_hash TEXT,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_bank_questions_teacher_id ON bank_questions(teacher_id);
CREATE INDEX IF NOT EXISTS idx_bank_questions_visibility ON bank_questions(visibility);
CREATE INDEX IF NOT EXISTS idx_bank_questions_text_hash ON bank_questions(text_hash);

CREATE TABLE IF NOT EXISTS moderation_queue (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  question_id INTEGER NOT NULL REFERENCES bank_questions(id) ON DELETE CASCADE,
  submitted_by TEXT NOT NULL,
  submitted_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  reviewed_by TEXT,
  reviewed_at TEXT,
  decision TEXT,                                -- approved | rejected
  admin_notes TEXT,
  priority INTEGER NOT NULL DEFAULT 5
);

CREATE TABLE IF NOT EXISTS question_interactions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  question_id INTEGER NOT NULL REFERENCES bank_questions(id) ON DELETE CASCADE,
  teacher_id TEXT NOT NULL,
  action_type TEXT NOT NULL,                    -- used | saved | copied | rated
  rating_value INTEGER,
  question_set_id INTEGER REFERENCES question_sets(id) ON DELETE SET NULL,
  paper_id INTEGER REFERENCES generated_papers(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  UNIQUE(question_id, teacher_id, action_type)
);

CREATE TABLE IF NOT EXISTS teacher_library (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  teacher_id TEXT NOT NULL,
  question_id INTEGER NOT NULL REFERENCES bank_questions(id) ON DELETE CASCADE,
  saved_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  notes TEXT,
  UNIQUE(teacher_id, question_id)
);

CREATE INDEX IF NOT EXISTS idx_teacher_library_teacher_id ON teacher_library(teacher_id);

CREATE TABLE IF NOT EXISTS teacher_badges (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  teacher_id TEXT NOT NULL,
  badge_slug TEXT NOT NULL,
  badge_name TEXT NOT NULL,
  badge_icon TEXT NOT NULL DEFAULT '🏆',
  awarded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  UNIQUE(teacher_id, badge_slug)
);

CREATE INDEX IF NOT EXISTS idx_teacher_badges_teacher_id ON teacher_badges(teacher_id);

CREATE TABLE IF NOT EXISTS publish_prompts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  teacher_id TEXT NOT NULL,
  paper_id INTEGER REFERENCES generated_papers(id) ON DELETE SET NULL,
  question_set_id INTEGER REFERENCES question_sets(id) ON DELETE SET NULL,
  question_ids TEXT NOT NULL,                   -- JSON array
  responded INTEGER NOT NULL DEFAULT 0,
  decision TEXT,
  published_ids TEXT,                           -- JSON array
  responded_at TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_publish_prompts_teacher_id ON publish_prompts(teacher_id);

CREATE TABLE IF NOT EXISTS teacher_notifications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  teacher_id TEXT NOT NULL,
  notif_type TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT,
  question_id INTEGER REFERENCES bank_questions(id) ON DELETE SET NULL,
  badge_slug TEXT,
  is_read INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_teacher_notifications_teacher_id ON teacher_notifications(teacher_id);

-- 8. Full-Text Search (FTS5) for Community Question Bank
CREATE VIRTUAL TABLE IF NOT EXISTS bank_questions_fts USING fts5(
  question_text,
  stem,
  topic,
  board,
  content='bank_questions',
  content_rowid='id',
  tokenize='unicode61'
);

CREATE TRIGGER IF NOT EXISTS bank_questions_ai AFTER INSERT ON bank_questions BEGIN
  INSERT INTO bank_questions_fts(rowid, question_text, stem, topic, board)
  VALUES (new.id, COALESCE(new.question_text, ''), COALESCE(new.stem, ''), COALESCE(new.topic, ''), COALESCE(new.board, ''));
END;

CREATE TRIGGER IF NOT EXISTS bank_questions_ad AFTER DELETE ON bank_questions BEGIN
  INSERT INTO bank_questions_fts(bank_questions_fts, rowid, question_text, stem, topic, board)
  VALUES ('delete', old.id, COALESCE(old.question_text, ''), COALESCE(old.stem, ''), COALESCE(old.topic, ''), COALESCE(old.board, ''));
END;

CREATE TRIGGER IF NOT EXISTS bank_questions_au AFTER UPDATE ON bank_questions BEGIN
  INSERT INTO bank_questions_fts(bank_questions_fts, rowid, question_text, stem, topic, board)
  VALUES ('delete', old.id, COALESCE(old.question_text, ''), COALESCE(old.stem, ''), COALESCE(old.topic, ''), COALESCE(old.board, ''));
  INSERT INTO bank_questions_fts(rowid, question_text, stem, topic, board)
  VALUES (new.id, COALESCE(new.question_text, ''), COALESCE(new.stem, ''), COALESCE(new.topic, ''), COALESCE(new.board, ''));
END;
