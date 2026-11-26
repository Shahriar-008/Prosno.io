import type { Bindings } from '../types';

/**
 * Optional Cloudflare Browser Rendering API helper.
 * When `env.BROWSER` is configured (Workers Paid + Browser Rendering binding),
 * renders HTML to a print-ready PDF buffer and optionally caches it in R2.
 * When `env.BROWSER` is absent (Free Tier), returns null cleanly so the caller
 * redirects or serves the instant HTML Print Studio.
 */
export async function renderHtmlToPdfBuffer(
  env: Bindings,
  htmlContent: string,
  cacheKey?: string
): Promise<ArrayBuffer | null> {
  if (cacheKey && env.PROSNO_R2) {
    const cached = await env.PROSNO_R2.get(cacheKey);
    if (cached) {
      return cached.arrayBuffer();
    }
  }

  if (!env.BROWSER) {
    return null;
  }

  try {
    // Support Cloudflare Browser Rendering REST/binding fetch interface
    const resp = await env.BROWSER.fetch('https://browser-rendering.cloudflare.internal/pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        html: htmlContent,
        pdfOptions: {
          printBackground: true,
          preferCSSPageSize: true,
        },
      }),
    });
    if (!resp.ok) return null;
    const pdfBuf = await resp.arrayBuffer();
    if (cacheKey && env.PROSNO_R2) {
      await env.PROSNO_R2.put(cacheKey, pdfBuf, {
        httpMetadata: { contentType: 'application/pdf' },
      });
    }
    return pdfBuf;
  } catch {
    return null;
  }
}
