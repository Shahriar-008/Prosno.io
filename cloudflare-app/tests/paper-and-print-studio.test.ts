import { describe, it, expect } from 'vitest';
import { createApp } from '../src/index';
import { createTestEnv, extractCookies } from './helpers/d1-sqlite';

describe('Paper Generation, Anti-Scraping & Live Print Studio', () => {
  it('supports guest custom paper + HTML Print Studio with Quick Answer Key, explanations & KaTeX', async () => {
    const app = createApp();
    const env = createTestEnv();

    const resp = await app.fetch(
      new Request('http://localhost/generate-custom-paper', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: 'বিজ্ঞান অধ্যায় ৫',
          time_minutes: 25,
          omr_style: true,
          questions: [
            {
              question_text: 'চোখের কোন অংশ ক্যামেরার ডায়াফ্রামের মতো কাজ করে?',
              type: 'simple',
              answer_options: ['রেটিনা', 'আইরিশ', 'কর্নিয়া', 'অক্ষিগোলক'],
              correct_answer: 'আইরিশ',
              explanation: 'আইরিশ পিউপিলের আকার নিয়ন্ত্রণ করে।',
              board: 'ঢা. বো.',
              year: 2020,
            },
            {
              question_text: 'যদি $x + \\frac{1}{x} = 3$ হয়, তবে $x^2 + \\frac{1}{x^2}$ কত?',
              type: 'simple',
              answer_options: ['5', '7', '9', '11'],
              correct_answer: '7',
              explanation: '$3^2 - 2 = 7$',
            },
          ],
        }),
      }),
      env
    );
    expect(resp.status).toBe(200);
    const data = (await resp.json()) as { paper_id: number; studio_url: string };
    expect(data.paper_id).toBeGreaterThan(0);

    const studioResp = await app.fetch(new Request(`http://localhost${data.studio_url}`), env);
    expect(studioResp.status).toBe(200);
    const html = await studioResp.text();
    expect(html).toContain('Hind Siliguri');
    expect(html).toContain('column-count: var(--paper-cols)');
    expect(html).toContain('omr-bubble');
    expect(html).toContain('দ্রুত উত্তর সংকেত');
    expect(html).toContain('আইরিশ পিউপিলের আকার নিয়ন্ত্রণ করে।');
    expect(html).toContain('math-tex');
  });

  it('enforces chapter limit, daily credits, teacher copy auth, and builder multi-section generation', async () => {
    const app = createApp();
    const env = createTestEnv();

    // Anti-scraping max chapters (>5)
    const tooMany = await app.fetch(
      new Request('http://localhost/get-questions-for-chapters', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chapter_ids: [1, 2, 3, 4, 5, 6] }),
      }),
      env
    );
    expect(tooMany.status).toBe(400);

    // Register teacher
    const reg = await app.fetch(
      new Request('http://localhost/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ display_name: 'Rahim', email: 'rahim@example.com', password: 'password123' }),
      }),
      env
    );
    const cookie = extractCookies(reg);

    // Builder multi-section MCQ + SQ + CQ
    const bldResp = await app.fetch(
      new Request('http://localhost/api/builder/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Cookie: cookie },
        body: JSON.stringify({
          paper_config: { title: 'পূর্ণাঙ্গ পরীক্ষা', time_minutes: 90, omr_style: true },
          sections: [
            { type: 'mcq', questions: [{ source: 'db', id: 1, db_source: 'db' }, { source: 'db', id: 2, db_source: 'db' }] },
            { type: 'sq', questions: [{ source: 'db', id: 1 }], answer_count: 1, marks_per_question: 2 },
            { type: 'cq', questions: [{ source: 'db', id: 1 }], answer_count: 1 },
          ],
        }),
      }),
      env
    );
    expect(bldResp.status).toBe(200);
    const bldData = (await bldResp.json()) as { paper_id: number; total_marks: number; studio_url: string };
    expect(bldData.total_marks).toBe(14); // 2 MCQ + 2 SQ + 10 CQ

    // Studio renders SQ & CQ sections + teacher copy hidden when unauthenticated
    const anonPrint = await app.fetch(new Request(`http://localhost/papers/${bldData.paper_id}/print?copy=answers`), env);
    expect(anonPrint.status).toBe(403);

    const authStudio = await app.fetch(new Request(`http://localhost${bldData.studio_url}`, { headers: { Cookie: cookie } }), env);
    const authHtml = await authStudio.text();
    expect(authHtml).toContain('খ-বিভাগ (সংক্ষিপ্ত প্রশ্ন)');
    expect(authHtml).toContain('গ-বিভাগ (সৃজনশীল প্রশ্ন)');

    // Persist Print Studio customization
    const cfgResp = await app.fetch(
      new Request(`http://localhost/api/papers/${bldData.paper_id}/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Cookie: cookie },
        body: JSON.stringify({
          studio: {
            font: 'tiro',
            columns: 3,
            instituteName: 'উদয়ন কোচিং',
            watermarkText: 'UDAYAN',
          },
        }),
      }),
      env
    );
    expect(cfgResp.status).toBe(200);
    const updatedStudioHtml = await (
      await app.fetch(new Request(`http://localhost${bldData.studio_url}`, { headers: { Cookie: cookie } }), env)
    ).text();
    expect(updatedStudioHtml).toContain('উদয়ন কোচিং');
    expect(updatedStudioHtml).toContain('UDAYAN');
  });

  it('saves, shares, and auto-grades public practice question sets', async () => {
    const app = createApp();
    const env = createTestEnv();

    const reg = await app.fetch(
      new Request('http://localhost/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ display_name: 'Salma', email: 'salma@example.com', password: 'password123' }),
      }),
      env
    );
    const cookie = extractCookies(reg);

    const saveResp = await app.fetch(
      new Request('http://localhost/save-question-set', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Cookie: cookie },
        body: JSON.stringify({
          name: 'Physics Set 1',
          questions: [
            { question_text: 'Q1', answer_options: ['A', 'B', 'C', 'D'], correct_answer: 'B' },
            { question_text: 'Q2', answer_options: ['1', '2', '3', '4'], correct_answer: '4' },
          ],
        }),
      }),
      env
    );
    expect(saveResp.status).toBe(201);
    const { id } = (await saveResp.json()) as { id: number };

    const shareResp = await app.fetch(
      new Request(`http://localhost/question-set/${id}/share`, { method: 'POST', headers: { Cookie: cookie } }),
      env
    );
    const { share_token } = (await shareResp.json()) as { share_token: string };
    expect(share_token).toBeTruthy();

    const subResp = await app.fetch(
      new Request(`http://localhost/paper/${share_token}/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ responses: { '0': 'B', '1': '1' } }),
      }),
      env
    );
    const scoreData = (await subResp.json()) as { score: number; total: number; percentage: number };
    expect(scoreData.score).toBe(1);
    expect(scoreData.total).toBe(2);
    expect(scoreData.percentage).toBe(50);
  });
});
