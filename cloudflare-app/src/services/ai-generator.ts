import type { Bindings } from '../types';
import { decryptSecret } from '../lib/crypto';
import { wordOverlapSimilarity } from '../lib/bengali';

export const DEFAULT_AI_PROMPT_TEMPLATE = `Subject: {subject_name}
Chapter: {chapter_name}
Class: {class_name}
Total_Questions: {count}

My Task: You are an expert on the Bangladesh NCTB {class_name} curriculum. Generate {count} Multiple Choice Questions (MCQs) in Bangla based on the subject and chapter above.
Output Format: Return ONLY a valid JSON array. Each item must have:
- question_text: (String)
- type: "simple" | "complex"
- sub_options: (Array of Strings, only if type is "complex")
- final_prompt: (String, only if type is "complex")
- answer_options: (Array of 4 Strings without ক/খ/গ/ঘ prefixes)
- correct_answer: (String matching one item in answer_options)
- explanation: (String, concise 1-2 line Bangla explanation)
- board: (Optional String like "ঢা. বো.")
- year: (Optional Integer like 2023)`;

interface GeneratedMcqItem {
  question_text: string;
  type?: string;
  sub_options?: string[];
  final_prompt?: string;
  answer_options: string[];
  correct_answer: string;
  explanation?: string;
  board?: string;
  year?: number;
}

function extractJsonArray(rawText: string): GeneratedMcqItem[] {
  let clean = rawText.trim();
  if (clean.includes('```json')) {
    clean = clean.split('```json')[1].split('```')[0].trim();
  } else if (clean.includes('```')) {
    clean = clean.split('```')[1].split('```')[0].trim();
  }
  const parsed = JSON.parse(clean);
  if (!Array.isArray(parsed)) throw new Error('AI response is not a JSON array');
  return parsed;
}

export async function callAiProvider(
  provider: string,
  apiKey: string,
  model: string,
  prompt: string
): Promise<{ questions: GeneratedMcqItem[]; tokensUsed: number }> {
  if (provider === 'openai') {
    const resp = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: model || 'gpt-4o-mini',
        messages: [
          {
            role: 'system',
            content: 'You are an expert NCTB Bangladesh educator. Always respond with valid JSON array only.',
          },
          { role: 'user', content: prompt },
        ],
        temperature: 0.7,
        max_tokens: 4000,
      }),
    });
    if (!resp.ok) {
      throw new Error(`OpenAI API Error ${resp.status}: ${await resp.text()}`);
    }
    const json = (await resp.json()) as {
      usage?: { total_tokens?: number };
      choices?: Array<{ message?: { content?: string } }>;
    };
    const content = json.choices?.[0]?.message?.content || '[]';
    return {
      questions: extractJsonArray(content),
      tokensUsed: json.usage?.total_tokens || 0,
    };
  }

  // Default: Gemini
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(
    model || 'gemini-2.0-flash'
  )}:generateContent?key=${encodeURIComponent(apiKey)}`;
  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      contents: [
        {
          parts: [
            {
              text: `You are a helpful assistant that generates educational MCQ questions. Always respond with valid JSON only.\n\n${prompt}`,
            },
          ],
        },
      ],
      generationConfig: {
        temperature: 0.7,
        maxOutputTokens: 4000,
        responseMimeType: 'application/json',
      },
    }),
  });
  if (!resp.ok) {
    throw new Error(`Gemini API Error ${resp.status}: ${await resp.text()}`);
  }
  const json = (await resp.json()) as {
    usageMetadata?: { totalTokenCount?: number };
    candidates?: Array<{ content?: { parts?: Array<{ text?: string }> } }>;
  };
  const content = json.candidates?.[0]?.content?.parts?.[0]?.text || '[]';
  return {
    questions: extractJsonArray(content),
    tokensUsed: json.usageMetadata?.totalTokenCount || 0,
  };
}

export async function runAiGenerationCycle(env: Bindings, force = false): Promise<{
  status: string;
  questionsGenerated: number;
  duplicatesFound: number;
  error?: string;
}> {
  const cfg = await env.DB.prepare('SELECT * FROM ai_generator_config LIMIT 1').first<{
    id: number;
    api_key: string | null;
    api_provider: string;
    model_name: string;
    prompt_template: string | null;
    questions_per_request: number;
    max_requests_per_hour: number;
    requests_this_hour: number;
    hour_started: string | null;
    is_running: number;
    current_class_id: number | null;
    current_subject_id: number | null;
    current_chapter_id: number | null;
  }>();

  if (!cfg || (!cfg.is_running && !force)) {
    return { status: 'skipped', questionsGenerated: 0, duplicatesFound: 0 };
  }

  const apiKey = await decryptSecret(cfg.api_key, env.ENCRYPTION_KEY || '');
  if (!apiKey) {
    return { status: 'error', questionsGenerated: 0, duplicatesFound: 0, error: 'Missing API key' };
  }

  const chapter = cfg.current_chapter_id
    ? await env.DB.prepare(
        `SELECT ch.id, ch.name, ch.name_bn, s.id as subject_id, s.name as subject_name, s.name_bn as subject_name_bn,
                c.id as class_id, c.name as class_name, c.name_bn as class_name_bn
         FROM chapters ch
         JOIN subjects s ON s.id = ch.subject_id
         JOIN classes c ON c.id = s.class_id
         WHERE ch.id = ?`
      )
        .bind(cfg.current_chapter_id)
        .first<{
          id: number;
          name: string;
          name_bn: string | null;
          subject_id: number;
          subject_name: string;
          subject_name_bn: string | null;
          class_id: number;
          class_name: string;
          class_name_bn: string | null;
        }>()
    : await env.DB.prepare(
        `SELECT ch.id, ch.name, ch.name_bn, s.id as subject_id, s.name as subject_name, s.name_bn as subject_name_bn,
                c.id as class_id, c.name as class_name, c.name_bn as class_name_bn
         FROM chapters ch
         JOIN subjects s ON s.id = ch.subject_id
         JOIN classes c ON c.id = s.class_id
         WHERE ch.is_active = 1
         ORDER BY c."order", s."order", ch."order" LIMIT 1`
      ).first<{
        id: number;
        name: string;
        name_bn: string | null;
        subject_id: number;
        subject_name: string;
        subject_name_bn: string | null;
        class_id: number;
        class_name: string;
        class_name_bn: string | null;
      }>();

  if (!chapter) {
    return { status: 'error', questionsGenerated: 0, duplicatesFound: 0, error: 'No active chapter found' };
  }

  const template = cfg.prompt_template || DEFAULT_AI_PROMPT_TEMPLATE;
  const prompt = template
    .replaceAll('{subject_name}', chapter.subject_name_bn || chapter.subject_name)
    .replaceAll('{chapter_name}', chapter.name_bn || chapter.name)
    .replaceAll('{class_name}', chapter.class_name_bn || chapter.class_name)
    .replaceAll('{count}', String(cfg.questions_per_request || 5));

  const t0 = Date.now();
  try {
    const { questions, tokensUsed } = await callAiProvider(cfg.api_provider, apiKey, cfg.model_name, prompt);
    const existingRows = await env.DB.prepare('SELECT question_text FROM questions WHERE chapter_id = ?')
      .bind(chapter.id)
      .all<{ question_text: string }>();
    const existingTexts = (existingRows.results || []).map((r) => r.question_text);

    let added = 0;
    let dupes = 0;
    for (const q of questions) {
      if (!q.question_text || !Array.isArray(q.answer_options) || q.answer_options.length < 4 || !q.correct_answer) {
        continue;
      }
      const isDupe = existingTexts.some((ex) => wordOverlapSimilarity(ex, q.question_text) > 0.8);
      if (isDupe) {
        dupes++;
        continue;
      }
      await env.DB.prepare(
        `INSERT INTO questions (question_text, question_type, sub_options, final_prompt, answer_options, correct_answer, explanation, board, year, chapter_id, is_active)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)`
      )
        .bind(
          q.question_text,
          q.type === 'complex' ? 'complex' : 'simple',
          q.type === 'complex' ? JSON.stringify(q.sub_options || []) : null,
          q.type === 'complex' ? q.final_prompt || 'নিচের কোনটি সঠিক?' : null,
          JSON.stringify(q.answer_options.slice(0, 4)),
          q.correct_answer,
          q.explanation || null,
          q.board || null,
          q.year || null,
          chapter.id
        )
        .run();
      existingTexts.push(q.question_text);
      added++;
    }

    const elapsed = (Date.now() - t0) / 1000;
    await env.DB.batch([
      env.DB.prepare(
        `INSERT INTO ai_generator_logs (class_id, subject_id, chapter_id, status, questions_generated, duplicates_found, tokens_used, api_response_time)
         VALUES (?, ?, ?, 'success', ?, ?, ?, ?)`
      ).bind(chapter.class_id, chapter.subject_id, chapter.id, added, dupes, tokensUsed, elapsed),
      env.DB.prepare(
        `UPDATE ai_generator_config
         SET last_run_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now'),
             total_questions_generated = total_questions_generated + ?,
             total_duplicates_skipped = total_duplicates_skipped + ?,
             requests_this_hour = requests_this_hour + 1
         WHERE id = ?`
      ).bind(added, dupes, cfg.id),
    ]);

    return { status: 'success', questionsGenerated: added, duplicatesFound: dupes };
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    await env.DB.batch([
      env.DB.prepare(
        `INSERT INTO ai_generator_logs (class_id, subject_id, chapter_id, status, error_message, api_response_time)
         VALUES (?, ?, ?, 'error', ?, ?)`
      ).bind(chapter.class_id, chapter.subject_id, chapter.id, msg, (Date.now() - t0) / 1000),
      env.DB.prepare('UPDATE ai_generator_config SET total_errors = total_errors + 1 WHERE id = ?').bind(cfg.id),
    ]);
    return { status: 'error', questionsGenerated: 0, duplicatesFound: 0, error: msg };
  }
}
