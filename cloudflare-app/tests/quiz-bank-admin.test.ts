import { describe, it, expect } from 'vitest';
import { createApp } from '../src/index';
import { createTestEnv, extractCookies } from './helpers/d1-sqlite';

describe('Live Quiz, Teacher Question Bank & Moderation', () => {
  it('runs a full Live Quiz flow from creation to student submission and CSV export', async () => {
    const app = createApp();
    const env = createTestEnv();

    const reg = await app.fetch(
      new Request('http://localhost/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ display_name: 'Quiz Master', email: 'qm@example.com', password: 'password123' }),
      }),
      env
    );
    const teacherCookie = extractCookies(reg);

    const qsResp = await app.fetch(
      new Request('http://localhost/save-question-set', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Cookie: teacherCookie },
        body: JSON.stringify({
          name: 'Live Quiz Set',
          questions: [
            { question_text: '2+2=?', answer_options: ['3', '4', '5', '6'], correct_answer: '4' },
          ],
        }),
      }),
      env
    );
    const { id: setId } = (await qsResp.json()) as { id: number };

    const createQuiz = await app.fetch(
      new Request('http://localhost/quiz/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Cookie: teacherCookie },
        body: JSON.stringify({ question_set_id: setId, title: 'Class 8 Quiz', shuffle_questions: false }),
      }),
      env
    );
    expect(createQuiz.status).toBe(200);
    const { quiz } = (await createQuiz.json()) as { quiz: { join_code: string } };

    // Student joins
    const joinResp = await app.fetch(
      new Request(`http://localhost/quiz/${quiz.join_code}/join`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'Student One' }),
      }),
      env
    );
    expect(joinResp.status).toBe(200);
    const studentCookie = extractCookies(joinResp);

    // Teacher starts quiz
    const startResp = await app.fetch(
      new Request(`http://localhost/quiz/${quiz.join_code}/start`, {
        method: 'POST',
        headers: { Cookie: teacherCookie },
      }),
      env
    );
    expect(startResp.status).toBe(200);

    // Student submits answer
    const submitResp = await app.fetch(
      new Request(`http://localhost/quiz/${quiz.join_code}/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Cookie: studentCookie },
        body: JSON.stringify({ responses: { '0': '4' }, time_taken_seconds: 12 }),
      }),
      env
    );
    const subData = (await submitResp.json()) as { score: number; total: number; percentage: number };
    expect(subData.score).toBe(1);
    expect(subData.percentage).toBe(100);

    // Teacher exports CSV
    const csvResp = await app.fetch(
      new Request(`http://localhost/quiz/${quiz.join_code}/export`, { headers: { Cookie: teacherCookie } }),
      env
    );
    expect(csvResp.status).toBe(200);
    const csvText = await csvResp.text();
    expect(csvText).toContain('1,"Student One",1,1,100%');
  });

  it('handles Community Bank submission, admin moderation, badges, notifications & FTS5 search', async () => {
    const app = createApp();
    const env = createTestEnv();

    // Bootstrap & login admin
    await app.fetch(
      new Request('http://localhost/api/auth/bootstrap-admin', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: 'admin', email: 'admin@prosno.io', password: 'adminpassword' }),
      }),
      env
    );
    const adminLogin = await app.fetch(
      new Request('http://localhost/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: 'admin@prosno.io', password: 'adminpassword' }),
      }),
      env
    );
    const adminCookie = extractCookies(adminLogin);

    // Register teacher & submit public question (enters moderation queue)
    const teacherReg = await app.fetch(
      new Request('http://localhost/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ display_name: 'Nadia', email: 'nadia@example.com', password: 'password123' }),
      }),
      env
    );
    const teacherCookie = extractCookies(teacherReg);

    const createQ = await app.fetch(
      new Request('http://localhost/api/v1/bank/questions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Cookie: teacherCookie },
        body: JSON.stringify({
          question_type: 'MCQ',
          question_text: 'আলোর প্রতিসরণের দ্বিতীয় সূত্র কার নামানুসারে পরিচিত?',
          answer_options: ['নিউটন', 'স্নেল', 'হাইগেন', 'গ্যালিলিও'],
          correct_answer: 'স্নেল',
          visibility: 'public',
        }),
      }),
      env
    );
    expect(createQ.status).toBe(201);
    const created = (await createQ.json()) as { id: number; visibility: string };
    expect(created.visibility).toBe('pending');

    // Admin inspects queue & approves
    const qResp = await app.fetch(
      new Request('http://localhost/api/v1/admin/bank/moderation/queue', { headers: { Cookie: adminCookie } }),
      env
    );
    const queue = (await qResp.json()) as { items: Array<{ id: number }> };
    expect(queue.items.length).toBe(1);

    const decResp = await app.fetch(
      new Request(`http://localhost/api/v1/admin/bank/moderation/${queue.items[0].id}/decide`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Cookie: adminCookie },
        body: JSON.stringify({ decision: 'approved' }),
      }),
      env
    );
    const decData = (await decResp.json()) as { decision: string; newly_awarded_badges: string[] };
    expect(decData.decision).toBe('approved');
    expect(decData.newly_awarded_badges).toContain('first_question');

    // FTS5 search finds the approved question
    const searchResp = await app.fetch(
      new Request(`http://localhost/api/v1/bank/search?q=${encodeURIComponent('প্রতিসরণের')}`),
      env
    );
    const searchData = (await searchResp.json()) as { items: Array<{ id: number }> };
    expect(searchData.items.some((x) => x.id === created.id)).toBe(true);

    // Teacher receives badge + approval notifications
    const notifResp = await app.fetch(
      new Request('http://localhost/api/v1/bank/notifications', { headers: { Cookie: teacherCookie } }),
      env
    );
    const notifData = (await notifResp.json()) as { notifications: Array<{ notif_type: string }> };
    expect(notifData.notifications.length).toBeGreaterThanOrEqual(2);
  });
});
