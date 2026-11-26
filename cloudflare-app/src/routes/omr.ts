import { Hono } from 'hono';
import type { AppContextEnv, OmrConfig } from '../types';
import { requireTeacher } from '../lib/auth';
import { rateLimit } from '../lib/rate-limit';
import {
  BUBBLE_SIZE_PRESETS,
  GENERAL_MAX_QUESTIONS_BY_COLUMN,
  THEME_COLORS,
  buildOmrHtml,
  getDefaultOmrConfig,
  normalizeOmrTemplateConfig,
} from '../services/omr-renderer';
import { renderHtmlToPdfBuffer } from '../services/browser-pdf';
import { renderPageLayout } from '../views/layout';
import { escapeHtml } from '../lib/math';

export const omrRoutes = new Hono<AppContextEnv>();

interface OmrRow {
  id: number;
  user_id: string;
  name: string;
  config_json: string;
  question_count: number;
  download_count: number;
  created_at: string;
  updated_at: string;
}

function serializeOmrRow(row: OmrRow) {
  let parsed: OmrConfig;
  try {
    parsed = normalizeOmrTemplateConfig(JSON.parse(row.config_json));
  } catch {
    parsed = getDefaultOmrConfig();
  }
  return {
    id: row.id,
    name: row.name,
    question_count: row.question_count,
    config_json: parsed,
    download_count: row.download_count || 0,
    created_at: row.created_at,
    updated_at: row.updated_at,
  };
}

omrRoutes.get('/omr-builder', (c) => {
  const user = c.get('user');
  const defaultCfg = getDefaultOmrConfig();
  const bootstrapJson = JSON.stringify({
    defaultConfig: defaultCfg,
    themeOptions: THEME_COLORS,
    bubbleSizes: BUBBLE_SIZE_PRESETS,
    generalMaxByCol: GENERAL_MAX_QUESTIONS_BY_COLUMN,
    isAuthenticated: Boolean(user),
  }).replace(/</g, '\\u003c');

  const html = renderPageLayout(
    {
      title: 'OMR Builder',
      description: 'Create scannable institutional and general OMR answer sheets with exact registration markers.',
      user,
      activeNav: 'omr',
      extraScripts: `<script id="omr-bootstrap" type="application/json">${bootstrapJson}</script><script src="/js/omr-builder.js"></script>`,
    },
    `<section class="page-section">
      <div class="container">
        <div class="page-hero">
          <div>
            <span class="badge-pill">Scannable OMR Studio</span>
            <h1>প্রিন্ট-রেডি ওএমআর (OMR) উত্তরপত্র ডিজাইনার</h1>
            <p>ইনস্টিটিউশনাল (৪০/৬০/৮০/১০০) এবং জেনারেল নরমাল (১-১০০) ওএমআর শিট লাইভ প্রিভিউ ও প্রিন্ট করুন।</p>
          </div>
          <div class="hero-actions">
            <button type="button" class="btn btn-primary" id="omrPrintBtn">প্রিন্ট / PDF ডাউনলোড</button>
          </div>
        </div>

        <div class="omr-workspace">
          <div class="omr-preview-pane">
            <div class="omr-chips">
              <span class="chip" id="omrChipVariant">Institutional</span>
              <span class="chip" id="omrChipCount">100 প্রশ্ন</span>
              <span class="chip" id="omrChipCols">4 কলাম</span>
            </div>
            <iframe id="omrPreviewFrame" title="OMR Live Preview" class="omr-iframe"></iframe>
          </div>

          <aside class="omr-controls-pane">
            ${user ? `
            <div class="card">
              <h3>সেভ করা টেমপ্লেট</h3>
              <label>টেমপ্লেটের নাম
                <input type="text" id="omrTplName" placeholder="Class 10 Final OMR">
              </label>
              <div class="row-actions">
                <select id="omrTplSelect"><option value="">টেমপ্লেট বাছাই করুন</option></select>
                <button type="button" class="btn btn-sm btn-outline" id="omrLoadBtn">লোড</button>
              </div>
              <div class="row-actions mt-2">
                <button type="button" class="btn btn-sm btn-primary" id="omrSaveBtn">সেভ</button>
                <button type="button" class="btn btn-sm btn-danger" id="omrDeleteBtn">ডিলিট</button>
              </div>
              <p class="muted small mt-1" id="omrTplStatus"></p>
            </div>` : '<div class="card"><p class="muted small">টেমপ্লেট সেভ করতে <a href="/login?next=/omr-builder">লগইন করুন</a>।</p></div>'}

            <div class="card">
              <h3>লেআউট ও থিম</h3>
              <label>ফরম্যাট
                <select id="omrVariant">
                  <option value="institutional">Institutional (স্ক্যান মার্কারসহ)</option>
                  <option value="general">General Normal (১-১০০)</option>
                </select>
              </label>
              <div id="omrInstCountWrap">
                <label>প্রশ্ন সংখ্যা
                  <select id="omrInstCount">
                    <option value="40">৪০</option>
                    <option value="60">৬০</option>
                    <option value="80">৮০</option>
                    <option value="100" selected>১০০</option>
                  </select>
                </label>
              </div>
              <div id="omrGenCountWrap" style="display:none;">
                <label>প্রশ্ন সংখ্যা (১-১০০)
                  <input type="number" id="omrGenCount" min="1" max="100" value="50">
                </label>
                <label>কলাম
                  <select id="omrGenCols">
                    <option value="1">Auto Flow</option>
                    <option value="2">২ কলাম (সর্বোচ্চ ৫০)</option>
                    <option value="3">৩ কলাম (সর্বোচ্চ ৭৫)</option>
                    <option value="4">৪ কলাম (সর্বোচ্চ ১০০)</option>
                  </select>
                </label>
              </div>
              <label>থিম রঙ
                <select id="omrTheme">
                  ${Object.entries(THEME_COLORS)
                    .map(([k, v]) => `<option value="${k}">${escapeHtml(v.label)}</option>`)
                    .join('')}
                </select>
              </label>
              <label>বাবল সাইজ
                <select id="omrBubbleSize">
                  <option value="large">Large (3.55mm)</option>
                  <option value="small">Small (3.10mm)</option>
                </select>
              </label>
              <label>হেডার মোড
                <select id="omrHeaderMode">
                  <option value="digital">Digital (টাইপ করা)</option>
                  <option value="manual">Manual (হাতে লেখার লাইন)</option>
                </select>
              </label>
            </div>

            <div class="card">
              <h3>প্রতিষ্ঠান ও পরীক্ষার তথ্য</h3>
              <label>শিরোনাম
                <input type="text" id="omrHeaderTitle" maxlength="80" placeholder="মডেল টেস্ট ২০২৬">
              </label>
              <label>উপশিরোনাম
                <input type="text" id="omrHeaderSubtitle" maxlength="120" placeholder="বিষয়: বিজ্ঞান">
              </label>
              <label>প্রতিষ্ঠানের নাম
                <input type="text" id="omrHeaderInstitution" maxlength="120" placeholder="উদয়ন কোচিং সেন্টার">
              </label>
              <div class="check-row">
                <label><input type="checkbox" id="omrFieldRoll" checked> রোল নম্বর</label>
                <label><input type="checkbox" id="omrFieldSubj" checked> বিষয় কোড</label>
                <label><input type="checkbox" id="omrFieldSet" checked> সেট কোড</label>
              </div>
              <label>নির্দেশাবলী (প্রতি লাইনে ১টি)
                <textarea id="omrInstructions" rows="4">${escapeHtml(defaultCfg.instructions.join('\n'))}</textarea>
              </label>
            </div>
          </aside>
        </div>
      </div>
    </section>`
  );
  return c.html(html);
});

omrRoutes.get('/api/omr/templates', requireTeacher, async (c) => {
  const user = c.get('user')!;
  const rows = await c.env.DB.prepare(
    'SELECT * FROM omr_templates WHERE user_id = ? ORDER BY updated_at DESC'
  )
    .bind(user.id)
    .all<OmrRow>();
  return c.json({ templates: (rows.results || []).map(serializeOmrRow) });
});

omrRoutes.post('/api/omr/templates', requireTeacher, rateLimit(30, 60, 'omr_create'), async (c) => {
  const user = c.get('user')!;
  const body = (await c.req.json().catch(() => ({}))) as { name?: string; config?: unknown };
  const name = (body.name || '').trim();
  if (!name || name.length > 200) {
    return c.json({ error: 'Template name is required (max 200 chars).' }, 400);
  }
  let cfg: OmrConfig;
  try {
    cfg = normalizeOmrTemplateConfig(body.config);
  } catch (err) {
    return c.json({ error: err instanceof Error ? err.message : 'Invalid OMR config' }, 400);
  }

  const ins = await c.env.DB.prepare(
    `INSERT INTO omr_templates (user_id, name, config_json, question_count) VALUES (?, ?, ?, ?)`
  )
    .bind(user.id, name, JSON.stringify(cfg), cfg.question_count)
    .run();

  const created = await c.env.DB.prepare('SELECT * FROM omr_templates WHERE id = ?')
    .bind(ins.meta.last_row_id)
    .first<OmrRow>();
  return c.json({ success: true, template: serializeOmrRow(created!) }, 201);
});

omrRoutes.get('/api/omr/templates/:id', requireTeacher, async (c) => {
  const user = c.get('user')!;
  const id = Number(c.req.param('id'));
  const row = await c.env.DB.prepare('SELECT * FROM omr_templates WHERE id = ? AND user_id = ?')
    .bind(id, user.id)
    .first<OmrRow>();
  if (!row) return c.json({ error: 'OMR template not found' }, 404);
  return c.json({ template: serializeOmrRow(row) });
});

omrRoutes.put('/api/omr/templates/:id', requireTeacher, async (c) => {
  const user = c.get('user')!;
  const id = Number(c.req.param('id'));
  const existing = await c.env.DB.prepare('SELECT * FROM omr_templates WHERE id = ? AND user_id = ?')
    .bind(id, user.id)
    .first<OmrRow>();
  if (!existing) return c.json({ error: 'OMR template not found' }, 404);

  const body = (await c.req.json().catch(() => ({}))) as { name?: string; config?: unknown };
  const name = (body.name ?? existing.name).trim();
  if (!name || name.length > 200) return c.json({ error: 'Invalid template name' }, 400);

  let cfg: OmrConfig;
  try {
    cfg = normalizeOmrTemplateConfig(body.config ?? JSON.parse(existing.config_json));
  } catch (err) {
    return c.json({ error: err instanceof Error ? err.message : 'Invalid OMR config' }, 400);
  }

  await c.env.DB.prepare(
    `UPDATE omr_templates
     SET name = ?, config_json = ?, question_count = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
     WHERE id = ? AND user_id = ?`
  )
    .bind(name, JSON.stringify(cfg), cfg.question_count, id, user.id)
    .run();

  const updated = await c.env.DB.prepare('SELECT * FROM omr_templates WHERE id = ?').bind(id).first<OmrRow>();
  return c.json({ success: true, template: serializeOmrRow(updated!) });
});

omrRoutes.post('/api/omr/templates/:id/delete', requireTeacher, async (c) => {
  const user = c.get('user')!;
  const id = Number(c.req.param('id'));
  const res = await c.env.DB.prepare('DELETE FROM omr_templates WHERE id = ? AND user_id = ?')
    .bind(id, user.id)
    .run();
  if (!res.meta.changes) return c.json({ error: 'OMR template not found' }, 404);
  return c.json({ success: true });
});

omrRoutes.post('/api/omr/render', rateLimit(30, 60, 'omr_render'), async (c) => {
  const body = (await c.req.json().catch(() => ({}))) as {
    config?: unknown;
    template_id?: number;
    format?: string;
    autoprint?: boolean;
  };
  let rawCfg = body.config;
  const user = c.get('user');

  if (body.template_id && user) {
    const row = await c.env.DB.prepare('SELECT * FROM omr_templates WHERE id = ? AND user_id = ?')
      .bind(body.template_id, user.id)
      .first<OmrRow>();
    if (!row) return c.json({ error: 'OMR template not found' }, 404);
    rawCfg = JSON.parse(row.config_json);
    await c.env.DB.prepare('UPDATE omr_templates SET download_count = download_count + 1 WHERE id = ?')
      .bind(row.id)
      .run();
  }

  let cfg: OmrConfig;
  try {
    cfg = normalizeOmrTemplateConfig(rawCfg);
  } catch (err) {
    return c.json({ error: err instanceof Error ? err.message : 'Invalid OMR config' }, 400);
  }

  const html = buildOmrHtml(cfg, Boolean(body.autoprint));
  if (body.format === 'pdf') {
    const pdfBuf = await renderHtmlToPdfBuffer(c.env, html);
    if (pdfBuf) {
      return new Response(pdfBuf, {
        headers: {
          'Content-Type': 'application/pdf',
          'Content-Disposition': 'attachment; filename="Prosno_OMR_Sheet.pdf"',
        },
      });
    }
  }
  return c.html(html);
});
