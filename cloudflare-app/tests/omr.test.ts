import { describe, it, expect } from 'vitest';
import { createApp } from '../src/index';
import { createTestEnv, extractCookies } from './helpers/d1-sqlite';

describe('OMR Builder & Millimeter Renderer', () => {
  it('validates institutional and general OMR configs, CRUD templates, and renders exact HTML', async () => {
    const app = createApp();
    const env = createTestEnv();

    // Render institutional 100Q OMR
    const renderInst = await app.fetch(
      new Request('http://localhost/api/omr/render', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          config: {
            template_type: 'exam_sheet_v1',
            sheet_variant: 'institutional',
            question_count: 100,
            theme_color: 'blue',
            header: { title: 'SSC Model Test', subtitle: 'Science', institution: 'Dhaka High' },
          },
        }),
      }),
      env
    );
    expect(renderInst.status).toBe(200);
    const instHtml = await renderInst.text();
    expect(instHtml).toContain('215.9mm 279.4mm');
    expect(instHtml).toContain('SSC Model Test');
    expect(instHtml).toContain('বহুনির্বাচনি অভীক্ষার উত্তরপত্র');

    // Reject invalid general column limit (2 cols max 50)
    const badGen = await app.fetch(
      new Request('http://localhost/api/omr/render', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          config: {
            template_type: 'exam_sheet_v1',
            sheet_variant: 'general',
            question_count: 70,
            answer_columns: 2,
          },
        }),
      }),
      env
    );
    expect(badGen.status).toBe(400);

    // Template CRUD
    const reg = await app.fetch(
      new Request('http://localhost/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ display_name: 'OMR Teacher', email: 'omr@example.com', password: 'password123' }),
      }),
      env
    );
    const cookie = extractCookies(reg);

    const createTpl = await app.fetch(
      new Request('http://localhost/api/omr/templates', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Cookie: cookie },
        body: JSON.stringify({
          name: '60Q Biology OMR',
          config: { template_type: 'exam_sheet_v1', sheet_variant: 'institutional', question_count: 60 },
        }),
      }),
      env
    );
    expect(createTpl.status).toBe(201);
    const { template } = (await createTpl.json()) as { template: { id: number; question_count: number } };
    expect(template.question_count).toBe(60);

    const listTpl = await app.fetch(new Request('http://localhost/api/omr/templates', { headers: { Cookie: cookie } }), env);
    const { templates } = (await listTpl.json()) as { templates: Array<{ id: number }> };
    expect(templates.length).toBe(1);
  });
});
