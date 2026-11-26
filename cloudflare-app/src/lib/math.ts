// Safe HTML escaping + hybrid KaTeX / legacy fraction & superscript formatter

export function escapeHtml(input: unknown): string {
  if (input === null || input === undefined) return '';
  return String(input)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

const SUPERSCRIPTS: Record<string, string> = {
  '⁰': '0',
  '¹': '1',
  '²': '2',
  '³': '3',
  '⁴': '4',
  '⁵': '5',
  '⁶': '6',
  '⁷': '7',
  '⁸': '8',
  '⁹': '9',
};

const SUBSCRIPTS: Record<string, string> = {
  '₀': '0',
  '₁': '1',
  '₂': '2',
  '₃': '3',
  '₄': '4',
  '₅': '5',
  '₆': '6',
  '₇': '7',
  '₈': '8',
  '₉': '9',
};

function formatPlainMathSegment(rawSegment: string): string {
  let result = escapeHtml(rawSegment);

  for (const [uni, digit] of Object.entries(SUPERSCRIPTS)) {
    result = result.split(uni).join(`<sup>${digit}</sup>`);
  }
  result = result.replace(/\^\{([^}]+)\}/g, '<sup>$1</sup>');
  result = result.replace(/\^([0-9a-zA-Z])/g, '<sup>$1</sup>');

  for (const [uni, digit] of Object.entries(SUBSCRIPTS)) {
    result = result.split(uni).join(`<sub>${digit}</sub>`);
  }

  // Legacy stacked fractions: (a+b)/(c+d) or 1/x
  const fracRe = /(\([^)]+\)|[a-zA-Z0-9]+)\s*\/\s*(\([^)]+\)|[a-zA-Z0-9]+)/g;
  result = result.replace(fracRe, (_m, rawNum: string, rawDen: string) => {
    let num = rawNum;
    let den = rawDen;
    if (num.startsWith('(') && num.endsWith(')')) num = num.slice(1, -1);
    if (den.startsWith('(') && den.endsWith(')')) den = den.slice(1, -1);
    return `<span class="frac"><span class="frac-num">${num}</span><span class="frac-den">${den}</span></span>`;
  });

  return result;
}

/**
 * Formats text safely for HTML output:
 * - Preserves `$...$` and `$$...$$` segments wrapped in `<span class="math-tex">` for KaTeX client rendering
 * - Converts legacy Prosno.io expressions (`1/x`, `x²`, `x^2`, `H₂O`) outside `$...$` into clean HTML fractions/sup/sub
 */
export function formatMathHtml(input: unknown): string {
  if (input === null || input === undefined) return '';
  const text = String(input);

  // Split by $$...$$ or $...$
  const tokenRegex = /(\$\$[\s\S]+?\$\$|\$[^$\n]+?\$)/g;
  const parts = text.split(tokenRegex);

  return parts
    .map((part) => {
      if (!part) return '';
      if (part.startsWith('$$') && part.endsWith('$$')) {
        const expr = part.slice(2, -2).trim();
        return `<span class="math-tex math-display" data-tex="${escapeHtml(expr)}">$$${escapeHtml(expr)}$$</span>`;
      }
      if (part.startsWith('$') && part.endsWith('$')) {
        const expr = part.slice(1, -1).trim();
        return `<span class="math-tex math-inline" data-tex="${escapeHtml(expr)}">$${escapeHtml(expr)}$</span>`;
      }
      return formatPlainMathSegment(part);
    })
    .join('');
}
