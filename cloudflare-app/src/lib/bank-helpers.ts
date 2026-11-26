import { computeTextHash } from './bengali';

const TRUST_MIN_APPROVED = 50;
const TRUST_MIN_ACCOUNT_AGE_DAYS = 30;
const TRUST_MIN_REPUTATION = 100;

export interface TeacherProfileRow {
  id: number;
  user_id: string;
  display_name: string | null;
  institute_name: string | null;
  institute_subtitle: string | null;
  logo_url: string | null;
  watermark_text: string | null;
  default_font: string | null;
  is_trusted: number;
  trust_granted_at: string | null;
  trust_granted_by: string | null;
  approved_questions_count: number;
  reputation_score: number;
  account_created_at: string;
  questions_created: number;
  questions_published: number;
  questions_used: number;
  total_downloads: number;
  average_rating: number;
  contributor_rank: string;
}

export function rankForScore(score: number): string {
  if (score >= 1000) return 'Master';
  if (score >= 500) return 'Expert';
  if (score >= 200) return 'Senior Contributor';
  if (score >= 50) return 'Contributor';
  return 'Newcomer';
}

export async function getOrCreateProfile(
  db: D1Database,
  userId: string,
  displayName?: string | null
): Promise<TeacherProfileRow> {
  let profile = await db
    .prepare('SELECT * FROM teacher_profiles WHERE user_id = ?')
    .bind(userId)
    .first<TeacherProfileRow>();

  if (!profile) {
    await db
      .prepare(
        `INSERT INTO teacher_profiles (user_id, display_name)
         VALUES (?, ?)`
      )
      .bind(userId, displayName || null)
      .run();
    profile = await db
      .prepare('SELECT * FROM teacher_profiles WHERE user_id = ?')
      .bind(userId)
      .first<TeacherProfileRow>();
  } else if (displayName && !profile.display_name) {
    await db
      .prepare('UPDATE teacher_profiles SET display_name = ? WHERE user_id = ?')
      .bind(displayName, userId)
      .run();
    profile.display_name = displayName;
  }

  return profile!;
}

export async function findDuplicates(
  db: D1Database,
  questionText: string,
  excludeId?: number
): Promise<Array<{ id: number; question_text: string; teacher_id: string }>> {
  const hash = await computeTextHash(questionText);
  const query = excludeId
    ? db
        .prepare(
          `SELECT id, question_text, teacher_id FROM bank_questions
           WHERE text_hash = ? AND visibility = 'public' AND is_active = 1 AND id != ?`
        )
        .bind(hash, excludeId)
    : db
        .prepare(
          `SELECT id, question_text, teacher_id FROM bank_questions
           WHERE text_hash = ? AND visibility = 'public' AND is_active = 1`
        )
        .bind(hash);
  const res = await query.all<{ id: number; question_text: string; teacher_id: string }>();
  return res.results || [];
}

export async function createNotification(
  db: D1Database,
  params: {
    teacherId: string;
    notifType: string;
    title: string;
    body?: string;
    questionId?: number | null;
    badgeSlug?: string | null;
  }
): Promise<void> {
  await db
    .prepare(
      `INSERT INTO teacher_notifications (teacher_id, notif_type, title, body, question_id, badge_slug)
       VALUES (?, ?, ?, ?, ?, ?)`
    )
    .bind(
      params.teacherId,
      params.notifType,
      params.title,
      params.body ?? null,
      params.questionId ?? null,
      params.badgeSlug ?? null
    )
    .run();
}

export async function refreshProfileCounters(db: D1Database, userId: string): Promise<TeacherProfileRow> {
  const createdRow = await db
    .prepare('SELECT COUNT(*) as cnt FROM bank_questions WHERE teacher_id = ? AND is_active = 1')
    .bind(userId)
    .first<{ cnt: number }>();

  const publishedRow = await db
    .prepare(`SELECT COUNT(*) as cnt FROM bank_questions WHERE teacher_id = ? AND visibility = 'public' AND is_active = 1`)
    .bind(userId)
    .first<{ cnt: number }>();

  const created = createdRow?.cnt || 0;
  const published = publishedRow?.cnt || 0;

  await db
    .prepare(
      `UPDATE teacher_profiles
       SET questions_created = ?, questions_published = ?, approved_questions_count = ?,
           updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
       WHERE user_id = ?`
    )
    .bind(created, published, published, userId)
    .run();

  return (await db
    .prepare('SELECT * FROM teacher_profiles WHERE user_id = ?')
    .bind(userId)
    .first<TeacherProfileRow>())!;
}

export async function recalculateReputation(db: D1Database, userId: string): Promise<TeacherProfileRow> {
  const profile = await getOrCreateProfile(db, userId);
  const agg = await db
    .prepare(
      `SELECT COALESCE(SUM(usage_count), 0) as total_used,
              COALESCE(SUM(download_count), 0) as total_dl,
              COALESCE(SUM(rating_total), 0) as r_total,
              COALESCE(SUM(rating_count), 0) as r_count
       FROM bank_questions
       WHERE teacher_id = ? AND visibility = 'public' AND is_active = 1`
    )
    .bind(userId)
    .first<{ total_used: number; total_dl: number; r_total: number; r_count: number }>();

  const totalUsed = agg?.total_used || 0;
  const totalDl = agg?.total_dl || 0;
  const rTotal = agg?.r_total || 0;
  const rCount = agg?.r_count || 0;
  const avgRating = rCount > 0 ? rTotal / rCount : 0;

  const score = Math.floor(
    profile.questions_published * 2 +
      totalUsed * 1 +
      avgRating * rCount * 5 +
      totalDl * 0.1
  );
  const roundedAvg = rCount > 0 ? Math.round(avgRating * 100) / 100 : 0;
  const rank = rankForScore(score);

  await db
    .prepare(
      `UPDATE teacher_profiles
       SET questions_used = ?, total_downloads = ?, average_rating = ?,
           reputation_score = ?, contributor_rank = ?,
           updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
       WHERE user_id = ?`
    )
    .bind(totalUsed, totalDl, roundedAvg, score, rank, userId)
    .run();

  return (await db
    .prepare('SELECT * FROM teacher_profiles WHERE user_id = ?')
    .bind(userId)
    .first<TeacherProfileRow>())!;
}

export async function maybeGrantAutoTrust(db: D1Database, profile: TeacherProfileRow): Promise<boolean> {
  if (profile.is_trusted) return false;
  const createdMs = new Date(profile.account_created_at || Date.now()).getTime();
  const ageDays = Math.floor((Date.now() - createdMs) / (1000 * 60 * 60 * 24));
  const qualifies =
    profile.approved_questions_count >= TRUST_MIN_APPROVED &&
    ageDays >= TRUST_MIN_ACCOUNT_AGE_DAYS &&
    profile.reputation_score >= TRUST_MIN_REPUTATION;

  if (!qualifies) return false;

  await db
    .prepare(
      `UPDATE teacher_profiles
       SET is_trusted = 1,
           trust_granted_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now'),
           trust_granted_by = 'system_auto'
       WHERE user_id = ?`
    )
    .bind(profile.user_id)
    .run();

  return true;
}

const STATIC_BADGES: Array<{
  slug: string;
  name: string;
  icon: string;
  check: (p: TeacherProfileRow) => boolean;
}> = [
  { slug: 'first_question', name: 'First Contribution', icon: '🌱', check: (p) => p.questions_published >= 1 },
  { slug: 'ten_published', name: '10 Questions Published', icon: '📝', check: (p) => p.questions_published >= 10 },
  { slug: 'hundred_published', name: '100 Questions Published', icon: '💯', check: (p) => p.questions_published >= 100 },
  { slug: 'thousand_published', name: '1000 Questions Published', icon: '🚀', check: (p) => p.questions_published >= 1000 },
  { slug: 'widely_used', name: 'Widely Used', icon: '🌍', check: (p) => (p.questions_used || 0) >= 1000 },
  {
    slug: 'highly_rated',
    name: 'Highly Rated',
    icon: '⭐',
    check: (p) => (p.average_rating || 0) >= 4.5 && p.questions_published >= 20,
  },
  { slug: 'contributor', name: 'Contributor', icon: '🎖️', check: (p) => p.reputation_score >= 50 },
  { slug: 'expert', name: 'Expert Teacher', icon: '🏅', check: (p) => p.reputation_score >= 500 },
];

export async function evaluateAndAwardBadges(db: D1Database, profile: TeacherProfileRow): Promise<string[]> {
  const existingRows = await db
    .prepare('SELECT badge_slug FROM teacher_badges WHERE teacher_id = ?')
    .bind(profile.user_id)
    .all<{ badge_slug: string }>();
  const existing = new Set((existingRows.results || []).map((r) => r.badge_slug));
  const newlyAwarded: string[] = [];

  async function award(slug: string, name: string, icon: string) {
    await db
      .prepare(
        `INSERT OR IGNORE INTO teacher_badges (teacher_id, badge_slug, badge_name, badge_icon)
         VALUES (?, ?, ?, ?)`
      )
      .bind(profile.user_id, slug, name, icon)
      .run();
    await createNotification(db, {
      teacherId: profile.user_id,
      notifType: 'badge_awarded',
      title: `${icon} Badge Earned: ${name}`,
      body: `Congratulations! You earned the "${name}" badge.`,
      badgeSlug: slug,
    });
    newlyAwarded.push(slug);
  }

  for (const defn of STATIC_BADGES) {
    if (!existing.has(defn.slug) && defn.check(profile)) {
      await award(defn.slug, defn.name, defn.icon);
    }
  }

  if (!existing.has('math_specialist')) {
    const row = await db
      .prepare(
        `SELECT COUNT(*) as cnt FROM bank_questions bq
         JOIN subjects s ON bq.subject_id = s.id
         WHERE bq.teacher_id = ? AND bq.visibility = 'public'
           AND (LOWER(s.name) LIKE '%math%' OR s.name_bn LIKE '%গণিত%')`
      )
      .bind(profile.user_id)
      .first<{ cnt: number }>();
    if ((row?.cnt || 0) >= 50) await award('math_specialist', 'Math Specialist', '🔢');
  }

  if (!existing.has('science_expert')) {
    const row = await db
      .prepare(
        `SELECT COUNT(*) as cnt FROM bank_questions bq
         JOIN subjects s ON bq.subject_id = s.id
         WHERE bq.teacher_id = ? AND bq.visibility = 'public'
           AND (LOWER(s.name) LIKE '%science%' OR LOWER(s.name) LIKE '%physics%'
                OR LOWER(s.name) LIKE '%chemistry%' OR LOWER(s.name) LIKE '%biology%'
                OR s.name_bn LIKE '%বিজ্ঞান%' OR s.name_bn LIKE '%পদার্থ%'
                OR s.name_bn LIKE '%রসায়ন%' OR s.name_bn LIKE '%জীববিজ্ঞান%')`
      )
      .bind(profile.user_id)
      .first<{ cnt: number }>();
    if ((row?.cnt || 0) >= 50) await award('science_expert', 'Science Expert', '🔬');
  }

  if (!existing.has('board_question_expert')) {
    const row = await db
      .prepare(
        `SELECT COUNT(*) as cnt FROM bank_questions
         WHERE teacher_id = ? AND visibility = 'public' AND board IS NOT NULL AND year IS NOT NULL`
      )
      .bind(profile.user_id)
      .first<{ cnt: number }>();
    if ((row?.cnt || 0) >= 20) await award('board_question_expert', 'Board Question Expert', '📋');
  }

  return newlyAwarded;
}

export async function postApprovalRefresh(
  db: D1Database,
  userId: string,
  question: { id: number; question_text: string; rejection_reason?: string | null } | null,
  decision: 'approved' | 'rejected'
): Promise<string[]> {
  await refreshProfileCounters(db, userId);
  const profile = await recalculateReputation(db, userId);
  await maybeGrantAutoTrust(db, profile);
  const newlyAwarded = await evaluateAndAwardBadges(db, profile);

  if (question) {
    const snippet = question.question_text.slice(0, 80);
    if (decision === 'approved') {
      await createNotification(db, {
        teacherId: userId,
        notifType: 'question_approved',
        title: '✅ Your question was approved!',
        body: `"${snippet}…" is now public in the Question Bank.`,
        questionId: question.id,
      });
    } else {
      await createNotification(db, {
        teacherId: userId,
        notifType: 'question_rejected',
        title: '❌ Your question was not approved',
        body: `"${snippet}…" was rejected. Reason: ${question.rejection_reason || 'See admin notes.'}`,
        questionId: question.id,
      });
    }
  }

  return newlyAwarded;
}
