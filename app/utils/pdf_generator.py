"""
PDF Generator for Question Papers (v2 - Table-based two-column layout)
Generates PDF files with two-column MCQ layout using ReportLab.
Uses a simple table-based layout approach for reliable two-column rendering.
"""
import gc
import io
import os
import re
import subprocess
import tempfile
import shutil
import logging
from typing import Optional, Union
from pathlib import Path

# Get module logger
logger = logging.getLogger(__name__)

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus import Flowable
from reportlab.platypus.flowables import Image as RLImage
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from .document_generator import to_bengali_numeral


# ---------------------------------------------------------------------------
# Math Expression Rendering (using matplotlib)
# ---------------------------------------------------------------------------
_MATH_RENDERER_AVAILABLE = False
try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    from matplotlib import mathtext
    _MATH_RENDERER_AVAILABLE = True
except ImportError:
    pass

# Cache for rendered math expressions (limited size to prevent memory issues)
_MATH_CACHE = {}
_MATH_CACHE_MAX_SIZE = 50  # Limit cache size for low-memory environments


def _clear_math_cache():
    """Clear the math expression cache to free memory."""
    global _MATH_CACHE
    _MATH_CACHE.clear()
    gc.collect()


def _cleanup_memory():
    """Force garbage collection to free memory in low-memory environments."""
    gc.collect()
    # Clear matplotlib figure cache if available
    if _MATH_RENDERER_AVAILABLE:
        try:
            plt.close('all')
        except Exception:
            pass


def _text_to_latex(text: str) -> str:
    """Convert common math notation to LaTeX format.
    
    Converts patterns like:
    - 1/x -> \\frac{1}{x}
    - x² -> x^{2}
    - x³ -> x^{3}
    - (a+b)² -> (a+b)^{2}
    """
    if not text:
        return text
    
    result = text
    
    # Convert Unicode superscripts to LaTeX
    superscript_map = {
        '²': '^{2}', '³': '^{3}', '⁴': '^{4}', '⁵': '^{5}',
        '⁶': '^{6}', '⁷': '^{7}', '⁸': '^{8}', '⁹': '^{9}', '⁰': '^{0}',
    }
    for uni, latex in superscript_map.items():
        result = result.replace(uni, latex)
    
    # Convert fraction patterns: a/b -> \frac{a}{b}
    # Handle complex patterns like (a+b)/(c+d), 1/x, etc.
    
    # Pattern for parenthesized expressions or single terms
    term_pattern = r'(\([^)]+\)|[a-zA-Z0-9]+)'
    fraction_pattern = rf'{term_pattern}\s*/\s*{term_pattern}'
    
    def replace_fraction(match):
        num, den = match.groups()
        # Remove outer parens if present for cleaner fractions
        if num.startswith('(') and num.endswith(')'):
            num = num[1:-1]
        if den.startswith('(') and den.endswith(')'):
            den = den[1:-1]
        return rf'\\frac{{{num}}}{{{den}}}'
    
    result = re.sub(fraction_pattern, replace_fraction, result)
    
    return result


def _render_math_to_image(latex_expr: str, fontsize: int = 10, dpi: int = 150) -> Optional[io.BytesIO]:
    """Render a LaTeX math expression to a PNG image buffer."""
    global _MATH_CACHE
    
    if not _MATH_RENDERER_AVAILABLE:
        return None
    
    cache_key = (latex_expr, fontsize, dpi)
    if cache_key in _MATH_CACHE:
        # Return a fresh copy of cached buffer
        cached = _MATH_CACHE[cache_key]
        buf = io.BytesIO(cached)
        buf.seek(0)
        return buf
    
    try:
        fig, ax = plt.subplots(figsize=(0.01, 0.01))
        ax.axis('off')
        
        # Render the math expression
        text = ax.text(0, 0, f'${latex_expr}$', fontsize=fontsize, 
                      verticalalignment='center', horizontalalignment='left')
        
        # Get the bounding box
        fig.canvas.draw()
        bbox = text.get_window_extent(fig.canvas.get_renderer())
        
        # Resize figure to fit text
        fig.set_size_inches(bbox.width / dpi + 0.1, bbox.height / dpi + 0.05)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        text.set_position((0.05, 0.5))
        
        # Save to buffer
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=dpi, transparent=True, 
                   bbox_inches='tight', pad_inches=0.02)
        plt.close(fig)
        
        # Cache the raw bytes (limit cache size to prevent memory issues)
        buf.seek(0)
        if len(_MATH_CACHE) >= _MATH_CACHE_MAX_SIZE:
            # Clear oldest entries when cache is full
            _MATH_CACHE.clear()
        _MATH_CACHE[cache_key] = buf.read()
        buf.seek(0)
        return buf
    except Exception:
        # Ensure figure is closed even on error
        try:
            plt.close('all')
        except Exception:
            pass
        return None


def _has_math_expression(text: str) -> bool:
    """Check if text contains math expressions that need special rendering."""
    if not text:
        return False
    # Check for fractions, exponents, or math operators
    math_indicators = [
        '/', '²', '³', '⁴', '⁵', '^',
        '√', '∛', '±', '×', '÷',
    ]
    return any(ind in text for ind in math_indicators)


def _has_fraction(text: str) -> bool:
    """Check if text contains a fraction pattern like a/b."""
    if not text or '/' not in text:
        return False
    # Pattern: term/term where term is (expr) or alphanumeric
    return bool(re.search(r'(\([^)]+\)|[a-zA-Z0-9]+)\s*/\s*(\([^)]+\)|[a-zA-Z0-9]+)', text))


def _format_math_html(text: str) -> str:
    """
    Convert math notation to HTML with proper superscripts and stacked fractions.
    
    Converts:
    - x² → x<sup>2</sup>
    - (1/x) → <span class='frac'>...</span> with stacked numerator/denominator
    
    Parameters:
        text (str): Input text potentially containing math expressions.
    
    Returns:
        str: HTML-formatted string with fractions and superscripts.
    """
    if not text:
        return text
    
    # First escape HTML entities
    result = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    
    # Convert Unicode superscripts to HTML <sup> tags
    superscript_map = {
        '⁰': '<sup>0</sup>', '¹': '<sup>1</sup>', '²': '<sup>2</sup>',
        '³': '<sup>3</sup>', '⁴': '<sup>4</sup>', '⁵': '<sup>5</sup>',
        '⁶': '<sup>6</sup>', '⁷': '<sup>7</sup>', '⁸': '<sup>8</sup>',
        '⁹': '<sup>9</sup>',
    }
    for uni, tag in superscript_map.items():
        result = result.replace(uni, tag)
    
    # Convert ^{...} notation to <sup>...</sup>
    result = re.sub(r'\^\{([^}]+)\}', r'<sup>\1</sup>', result)
    
    # Convert simple ^n notation (single digit/letter) to <sup>
    result = re.sub(r'\^([0-9a-zA-Z])', r'<sup>\1</sup>', result)
    
    # Convert Unicode subscripts to HTML <sub> tags
    subscript_map = {
        '₀': '<sub>0</sub>', '₁': '<sub>1</sub>', '₂': '<sub>2</sub>',
        '₃': '<sub>3</sub>', '₄': '<sub>4</sub>', '₅': '<sub>5</sub>',
        '₆': '<sub>6</sub>', '₇': '<sub>7</sub>', '₈': '<sub>8</sub>',
        '₉': '<sub>9</sub>',
    }
    for uni, tag in subscript_map.items():
        result = result.replace(uni, tag)
    
    # Convert fractions: (expr)/term or term/term => stacked fraction HTML
    # Pattern: (complex) / term, term / (complex), term/term
    term_pattern = r'(\([^)]+\)|[a-zA-Z0-9]+)'
    
    def make_fraction_html(match):
        """Build HTML for a stacked fraction."""
        num, den = match.groups()
        # Strip outer parens for cleaner display
        if num.startswith('(') and num.endswith(')'):
            num = num[1:-1]
        if den.startswith('(') and den.endswith(')'):
            den = den[1:-1]
        return (
            f"<span class='frac'>"
            f"<span class='frac-num'>{num}</span>"
            f"<span class='frac-den'>{den}</span>"
            f"</span>"
        )
    
    result = re.sub(rf'{term_pattern}\s*/\s*{term_pattern}', make_fraction_html, result)
    
    return result


def _format_math_text(text: str) -> str:
    """Convert math notation to ReportLab's Paragraph-compatible markup.
    
    Converts:
    - x² → x<super>2</super>
    - x³ → x<super>3</super>  
    - x^2 → x<super>2</super>
    - x^{12} → x<super>12</super>
    - 1/x → <super>1</super>/<sub>x</sub> (inline fraction)
    
    Inline fractions are rendered as superscript numerator / subscript denominator
    to maintain text flow without breaking lines.
    """
    if not text:
        return text
    
    result = text
    
    # Convert fractions FIRST (before super/subscript handling)
    # Pattern: (expr)/term, term/(expr), term/term
    # Uses inline format: superscript numerator / subscript denominator
    term_pattern = r'(\([^)]+\)|[a-zA-Z0-9]+)'
    
    def make_inline_fraction(match):
        """Build inline fraction using super/sub tags for compact display."""
        num, den = match.groups()
        # Strip outer parens for cleaner display
        if num.startswith('(') and num.endswith(')'):
            num = num[1:-1]
        if den.startswith('(') and den.endswith(')'):
            den = den[1:-1]
        # Use fraction slash (U+2044) for better visual separation
        return f'<super>{num}</super>\u2044<sub>{den}</sub>'
    
    result = re.sub(rf'{term_pattern}\s*/\s*{term_pattern}', make_inline_fraction, result)
    
    # Convert Unicode superscripts to <super> tags
    superscript_map = {
        '⁰': '<super>0</super>',
        '¹': '<super>1</super>',
        '²': '<super>2</super>',
        '³': '<super>3</super>',
        '⁴': '<super>4</super>',
        '⁵': '<super>5</super>',
        '⁶': '<super>6</super>',
        '⁷': '<super>7</super>',
        '⁸': '<super>8</super>',
        '⁹': '<super>9</super>',
    }
    for uni, tag in superscript_map.items():
        result = result.replace(uni, tag)
    
    # Convert ^{...} notation to <super>...</super>
    result = re.sub(r'\^\{([^}]+)\}', r'<super>\1</super>', result)
    
    # Convert simple ^n notation (single digit/letter) to <super>
    result = re.sub(r'\^([0-9a-zA-Z])', r'<super>\1</super>', result)
    
    # Convert Unicode subscripts to <sub> tags
    subscript_map = {
        '₀': '<sub>0</sub>',
        '₁': '<sub>1</sub>',
        '₂': '<sub>2</sub>',
        '₃': '<sub>3</sub>',
        '₄': '<sub>4</sub>',
        '₅': '<sub>5</sub>',
        '₆': '<sub>6</sub>',
        '₇': '<sub>7</sub>',
        '₈': '<sub>8</sub>',
        '₉': '<sub>9</sub>',
    }
    for uni, tag in subscript_map.items():
        result = result.replace(uni, tag)
    
    return result


def _is_pure_math(text: str) -> bool:
    """Check if text is purely mathematical (no Bengali/other scripts).
    
    Returns True if text only contains ASCII letters, numbers, math symbols.
    """
    if not text:
        return False
    # Math-safe characters
    allowed = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
                  '+-*/=()[]{}^²³⁴⁵⁶⁷⁸⁹⁰₀₁₂₃₄₅₆₇₈₉. ')
    return all(c in allowed for c in text)


def _to_latex(text: str) -> str:
    """Convert math expression to LaTeX for matplotlib rendering."""
    result = text
    
    # Convert Unicode superscripts to LaTeX
    sup_map = {'²': '^{2}', '³': '^{3}', '⁴': '^{4}', '⁵': '^{5}',
               '⁶': '^{6}', '⁷': '^{7}', '⁸': '^{8}', '⁹': '^{9}', '⁰': '^{0}'}
    for uni, latex in sup_map.items():
        result = result.replace(uni, latex)
    
    # Convert subscripts
    sub_map = {'₀': '_{0}', '₁': '_{1}', '₂': '_{2}', '₃': '_{3}', '₄': '_{4}',
               '₅': '_{5}', '₆': '_{6}', '₇': '_{7}', '₈': '_{8}', '₉': '_{9}'}
    for uni, latex in sub_map.items():
        result = result.replace(uni, latex)
    
    # Convert fractions: a/b -> \frac{a}{b}
    # Handle (expr)/term, term/(expr), (expr)/(expr), term/term
    def replace_frac(m):
        num, den = m.group(1), m.group(2)
        # Strip outer parens for cleaner fractions
        if num.startswith('(') and num.endswith(')'):
            num = num[1:-1]
        if den.startswith('(') and den.endswith(')'):
            den = den[1:-1]
        return rf'\\frac{{{num}}}{{{den}}}'
    
    # Match fractions: (complex expr) / (complex expr) or simple/simple
    term = r'(\([^)]+\)|[a-zA-Z0-9^{}]+)'
    result = re.sub(rf'{term}\s*/\s*{term}', replace_frac, result)
    
    return result


def _parse_fraction_from_text(text: str) -> tuple:
    """Parse a fraction pattern from text, returns (before, numerator, denominator, after) or None."""
    if not text or '/' not in text:
        return None
    # Pattern for fractions: (expr)/term, term/(expr), (expr)/(expr), term/term
    pattern = r'(.*?)(\([^)]+\)|[a-zA-Z0-9]+)\s*/\s*(\([^)]+\)|[a-zA-Z0-9]+)(.*)'
    match = re.match(pattern, text, re.DOTALL)
    if match:
        before, num, den, after = match.groups()
        # Strip outer parentheses if present
        if num.startswith('(') and num.endswith(')'):
            num = num[1:-1]
        if den.startswith('(') and den.endswith(')'):
            den = den[1:-1]
        return before.strip(), num.strip(), den.strip(), after.strip()
    return None


class FractionFlowable(Flowable):
    """Flowable that renders a stacked fraction (numerator over denominator)."""
    
    def __init__(self, numerator: str, denominator: str, style: ParagraphStyle, 
                 max_width: float = 50):
        super().__init__()
        self.numerator = numerator
        self.denominator = denominator
        self.style = style
        self.max_width = max_width
        self._width = 0
        self._height = 0
        self._num_para = None
        self._den_para = None
    
    def wrap(self, availWidth, availHeight):
        # Create smaller style for fraction parts
        frac_style = ParagraphStyle(
            'FractionPart',
            fontName=self.style.fontName,
            fontSize=self.style.fontSize * 0.8,  # Slightly smaller
            leading=self.style.fontSize * 0.9,
            alignment=TA_CENTER,
        )
        
        self._num_para = Paragraph(_escape(self.numerator), frac_style)
        self._den_para = Paragraph(_escape(self.denominator), frac_style)
        
        num_w, num_h = self._num_para.wrap(self.max_width, availHeight)
        den_w, den_h = self._den_para.wrap(self.max_width, availHeight)
        
        self._width = max(num_w, den_w) + 4  # Add padding
        self._height = num_h + den_h + 3  # Space for fraction line
        
        return self._width, self._height
    
    def draw(self):
        c = self.canv
        
        # Calculate positions
        num_w, num_h = self._num_para.wrap(self._width, 100)
        den_w, den_h = self._den_para.wrap(self._width, 100)
        
        # Draw numerator (on top)
        num_x = (self._width - num_w) / 2
        num_y = den_h + 3  # Above the line
        self._num_para.drawOn(c, num_x, num_y)
        
        # Draw fraction line
        c.saveState()
        c.setLineWidth(0.5)
        c.setStrokeColor(colors.black)
        c.line(0, den_h + 1.5, self._width, den_h + 1.5)
        c.restoreState()
        
        # Draw denominator (below)
        den_x = (self._width - den_w) / 2
        self._den_para.drawOn(c, den_x, 0)


class MathTextFlowable(Flowable):
    """Flowable that renders text with inline fractions and superscripts."""
    
    def __init__(self, text: str, style: ParagraphStyle):
        super().__init__()
        self.text = text
        self.style = style
        self._parts = []  # List of (flowable, width, height)
        self._width = 0
        self._height = 0
        self._wrapped = False
    
    def _build_parts(self, availWidth: float) -> list:
        """Parse text and build list of flowables/strings."""
        parts = []
        remaining = self.text
        
        while remaining:
            frac = _parse_fraction_from_text(remaining)
            if frac:
                before, num, den, after = frac
                if before:
                    parts.append(('text', before))
                parts.append(('fraction', num, den))
                remaining = after
            else:
                parts.append(('text', remaining))
                break
        
        return parts
    
    def wrap(self, availWidth, availHeight):
        if self._wrapped:
            return self._width, self._height
            
        parts = self._build_parts(availWidth)
        
        total_width = 0
        max_height = self.style.fontSize + 2  # Minimum height
        self._parts = []
        
        for part in parts:
            if part[0] == 'text':
                # Apply math formatting (superscripts, etc.)
                formatted = _format_math_text(part[1])
                # Escape only if there are no existing tags
                if '<' not in formatted:
                    formatted = _escape(formatted)
                para = Paragraph(formatted, self.style)
                try:
                    w, h = para.wrap(max(availWidth - total_width, 50), availHeight)
                except Exception:
                    # Fallback for problematic text
                    para = Paragraph(_escape(part[1]), self.style)
                    w, h = para.wrap(max(availWidth - total_width, 50), availHeight)
                self._parts.append((para, w, h))
                total_width += w
                max_height = max(max_height, h)
            elif part[0] == 'fraction':
                frac = FractionFlowable(part[1], part[2], self.style)
                w, h = frac.wrap(50, availHeight)
                self._parts.append((frac, w, h))
                total_width += w + 2  # Add small gap
                max_height = max(max_height, h)
        
        self._width = min(total_width, availWidth) if total_width > 0 else availWidth
        self._height = max_height
        self._wrapped = True
        return self._width, self._height
    
    def draw(self):
        x = 0
        for flowable, w, h in self._parts:
            # Vertically center each part
            y_offset = (self._height - h) / 2
            flowable.drawOn(self.canv, x, y_offset)
            x += w + 2


class MathImageFlowable(Flowable):
    """Flowable that renders a math expression as an image using matplotlib."""
    
    def __init__(self, latex_expr: str, fontsize: int = 10, maxwidth: float = 100):
        super().__init__()
        self.latex_expr = latex_expr
        self.fontsize = fontsize
        self.maxwidth = maxwidth
        self._img_reader = None
        self._img_width = 0
        self._img_height = 0
    
    def wrap(self, availWidth, availHeight):
        if self._img_reader is None and _MATH_RENDERER_AVAILABLE:
            img_buf = _render_math_to_image(self.latex_expr, self.fontsize)
            if img_buf:
                from reportlab.lib.utils import ImageReader
                from PIL import Image
                img = Image.open(img_buf)
                # Scale to reasonable size (72 DPI)
                scale = 72 / 150  # dpi ratio
                self._img_width = min(img.width * scale, self.maxwidth)
                self._img_height = img.height * scale * (self._img_width / (img.width * scale))
                img_buf.seek(0)
                self._img_reader = ImageReader(img_buf)
        
        return (self._img_width, self._img_height) if self._img_reader else (0, 0)
    
    def draw(self):
        if self._img_reader:
            self.canv.drawImage(
                self._img_reader, 0, 0,
                width=self._img_width, height=self._img_height,
                mask='auto'
            )


# --- WeasyPrint HTML renderer helper ---
def _build_html(questions: list, paper_config: dict, show_answer: bool, omr_style: bool = True) -> str:
    """
    Return HTML string for the question paper with proper math rendering.
    
    Uses CSS-based stacked fractions and superscripts for math expressions.
    Uses local font files via file:// URIs for Bengali text support.
    
    Parameters:
        questions (list): List of question dicts with question_text, answer_options, etc.
        paper_config (dict): Paper configuration with title, class_name, subject_name, time, marks.
        show_answer (bool): If True, highlight correct answers.
        omr_style (bool): If True, show OMR circles beside options.
    
    Returns:
        str: Complete HTML document as a string.
    """
    # locate fonts
    fonts_dir = Path(_FONTS_DIR)
    regular = fonts_dir.joinpath('NotoSansBengali-Regular.ttf').as_uri()
    bold = fonts_dir.joinpath('NotoSansBengali-Bold.ttf').as_uri() if fonts_dir.joinpath('NotoSansBengali-Bold.ttf').exists() else regular

    def esc(s):
        """Escape HTML entities without math formatting."""
        return (str(s) if s is not None else '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    def format_math(s):
        """Format text with math expressions (fractions, superscripts)."""
        return _format_math_html(str(s) if s is not None else '')

    title = esc(paper_config.get('title', 'Home Test'))
    class_name = esc(paper_config.get('class_name', ''))
    subject_name = esc(paper_config.get('subject_name', ''))
    bengali_time = to_bengali_numeral(paper_config.get('time', len(questions)))
    bengali_marks = to_bengali_numeral(paper_config.get('marks', len(questions)))

    # CSS: two columns, fractions, and simple table for options
    css = f"""
    @font-face {{
        font-family: 'NotoSansBengaliLocal';
        src: url('{regular}');
        font-weight: normal;
    }}
    @font-face {{
        font-family: 'NotoSansBengaliLocal';
        src: url('{bold}');
        font-weight: bold;
    }}
    body {{ font-family: 'NotoSansBengaliLocal', sans-serif; font-size: 12px; }}
    .container {{ width: 100%; max-width: 800px; margin: 0 auto; }}
    .header {{ text-align:center; }}
    .meta {{ display:flex; justify-content:space-between; margin-bottom:8px; }}
    .questions {{ column-count: 2; column-gap: 24px; }}
    .question {{ break-inside: avoid; margin-bottom:6px; }}
    .qtext {{ font-weight:700; margin-bottom:4px; }}
    .opts {{ width:100%; border-collapse:collapse; }}
    .opts td {{ vertical-align:top; padding:2px 6px 2px 0; }}
    .circle {{ display:inline-block; width:12px; height:12px; border-radius:50%; border:1px solid #000; margin-right:6px; vertical-align:middle; }}
    .circle.filled {{ background:#000; }}
    /* Stacked fraction styles */
    .frac {{
        display: inline-flex;
        flex-direction: column;
        align-items: center;
        vertical-align: middle;
        margin: 0 2px;
        font-size: 0.85em;
    }}
    .frac-num {{
        border-bottom: 1px solid #000;
        padding: 0 3px 1px 3px;
        line-height: 1.1;
    }}
    .frac-den {{
        padding: 1px 3px 0 3px;
        line-height: 1.1;
    }}
    /* Superscript styling */
    sup {{
        font-size: 0.7em;
        vertical-align: super;
        line-height: 0;
    }}
    sub {{
        font-size: 0.7em;
        vertical-align: sub;
        line-height: 0;
    }}
    """

    # Build questions HTML
    q_html = []
    for idx, q in enumerate(questions, 1):
        qid = esc(q.get('id', idx))
        qtext = format_math(q.get('question_text', ''))
        q_block = [f"<div class='question'><div class='qtext'>{qid}. {qtext}</div>"]
        # complex sub-options
        if q.get('type') == 'complex':
            for sub in q.get('sub_options', []):
                q_block.append(f"<div class='sub'>{format_math(sub)}</div>")
            q_block.append(f"<div class='prompt'><strong>{esc(q.get('final_prompt','নিচের কোনটি সঠিক?'))}</strong></div>")

        opts = q.get('answer_options', [])
        correct = str(q.get('correct_answer', '')).strip()
        if len(opts) >= 4:
            # two-row 2x2 table
            q_block.append("<table class='opts'><tr>")
            for i in range(4):
                opt_text = format_math(opts[i])
                is_correct = show_answer and (str(opts[i]).strip() == correct)
                circle_html = ''
                if omr_style:
                    circle_cls = 'circle filled' if is_correct else 'circle'
                    circle_html = f"<span class='{circle_cls}'></span>"
                # prefix Bengali letters
                prefix = ['ক)', 'খ)', 'গ)', 'ঘ)'][i]
                q_block.append(f"<td>{circle_html}{prefix} {opt_text}</td>")
                if i % 2 == 1 and i != 3:
                    q_block.append('</tr><tr>')
            q_block.append('</tr></table>')
        else:
            for i, opt in enumerate(opts):
                is_correct = show_answer and (str(opt).strip() == correct)
                circle_html = ''
                if omr_style:
                    circle_cls = 'circle filled' if is_correct else 'circle'
                    circle_html = f"<span class='{circle_cls}'></span>"
                prefix = ['ক)', 'খ)', 'গ)', 'ঘ)'][i] if i < 4 else ''
                q_block.append(f"<div>{circle_html}{prefix} {format_math(opt)}</div>")

        q_block.append('</div>')
        q_html.append(''.join(q_block))

    html = f"""
    <html>
    <head>
        <meta charset='utf-8'/>
        <style>{css}</style>
    </head>
    <body>
        <div class='container'>
            <div class='header'>
                <h1>{title}</h1>
                <div>{class_name}</div>
                <div>{subject_name}</div>
            </div>
            <div class='meta'>
                <div>সময়— {bengali_time} মিনিট</div>
                <div>পূর্ণমান— {bengali_marks}</div>
            </div>
            <div class='questions'>
                {''.join(q_html)}
            </div>
        </div>
    </body>
    </html>
    """
    return html


# ---------------------------------------------------------------------------
# Font Registration
# ---------------------------------------------------------------------------
_FONTS_REGISTERED = False

_FONTS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..', 'static', 'fonts',
)

FONT_REGULAR = 'NotoSansBengali'
FONT_BOLD = 'NotoSansBengali-Bold'


def _register_fonts() -> None:
    """Register Noto Sans Bengali TTF fonts with ReportLab (once)."""
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return

    regular_path = os.path.join(_FONTS_DIR, 'NotoSansBengali-Regular.ttf')
    bold_path = os.path.join(_FONTS_DIR, 'NotoSansBengali-Bold.ttf')

    if not os.path.exists(regular_path):
        raise FileNotFoundError(
            f"Bengali font not found: {regular_path}. "
            "Please place NotoSansBengali-Regular.ttf in app/static/fonts/."
        )

    pdfmetrics.registerFont(TTFont(FONT_REGULAR, regular_path))

    if os.path.exists(bold_path):
        pdfmetrics.registerFont(TTFont(FONT_BOLD, bold_path))
    else:
        pdfmetrics.registerFont(TTFont(FONT_BOLD, regular_path))

    from reportlab.pdfbase.pdfmetrics import registerFontFamily
    registerFontFamily(
        FONT_REGULAR,
        normal=FONT_REGULAR,
        bold=FONT_BOLD,
        italic=FONT_REGULAR,
        boldItalic=FONT_BOLD,
    )

    _FONTS_REGISTERED = True


# ---------------------------------------------------------------------------
# Layout Constants (matching DOCX)
# ---------------------------------------------------------------------------
_PAGE_WIDTH, _PAGE_HEIGHT = A4
_LEFT_MARGIN = 0.75 * inch
_RIGHT_MARGIN = 0.75 * inch
_TOP_MARGIN = 0.5 * inch
_BOTTOM_MARGIN = 0.5 * inch
_COLUMN_GAP = 0.35 * inch  # Gap between columns

_USABLE_WIDTH = _PAGE_WIDTH - _LEFT_MARGIN - _RIGHT_MARGIN
_COL_WIDTH = (_USABLE_WIDTH - _COLUMN_GAP) / 2

# Font sizes matching DOCX
_Q_FONT_SIZE = 8
_HEADER_FONT_SIZE = 10
_TITLE_FONT_SIZE = 14
_LEADING = 10


# ---------------------------------------------------------------------------
# Styles (cached globally for performance)
# ---------------------------------------------------------------------------
_CACHED_STYLES = None


def _build_styles() -> dict:
    """Build ParagraphStyle objects. Cached after first call."""
    global _CACHED_STYLES
    if _CACHED_STYLES is not None:
        return _CACHED_STYLES
    
    _CACHED_STYLES = {
        'title': ParagraphStyle(
            'PaperTitle',
            fontName=FONT_BOLD,
            fontSize=_TITLE_FONT_SIZE,
            leading=_TITLE_FONT_SIZE + 2,
            alignment=TA_CENTER,
            spaceAfter=2,
        ),
        'center': ParagraphStyle(
            'CenterText',
            fontName=FONT_REGULAR,
            fontSize=_HEADER_FONT_SIZE,
            leading=_HEADER_FONT_SIZE + 2,
            alignment=TA_CENTER,
            spaceAfter=1,
        ),
        'header_left': ParagraphStyle(
            'HeaderLeft',
            fontName=FONT_REGULAR,
            fontSize=_HEADER_FONT_SIZE,
            leading=_HEADER_FONT_SIZE + 2,
            alignment=TA_LEFT,
        ),
        'header_right': ParagraphStyle(
            'HeaderRight',
            fontName=FONT_REGULAR,
            fontSize=_HEADER_FONT_SIZE,
            leading=_HEADER_FONT_SIZE + 2,
            alignment=TA_RIGHT,
        ),
        'question': ParagraphStyle(
            'QuestionText',
            fontName=FONT_BOLD,
            fontSize=_Q_FONT_SIZE,
            leading=_LEADING,
            spaceBefore=3,
            spaceAfter=0,
        ),
        'sub_option': ParagraphStyle(
            'SubOption',
            fontName=FONT_REGULAR,
            fontSize=_Q_FONT_SIZE,
            leading=_LEADING,
            leftIndent=6,
            spaceAfter=0,
        ),
        'prompt': ParagraphStyle(
            'Prompt',
            fontName=FONT_BOLD,
            fontSize=_Q_FONT_SIZE,
            leading=_LEADING,
            spaceAfter=0,
        ),
        'option_normal': ParagraphStyle(
            'OptionNormal',
            fontName=FONT_REGULAR,
            fontSize=_Q_FONT_SIZE,
            leading=_LEADING,
        ),
        'option_bold': ParagraphStyle(
            'OptionBold',
            fontName=FONT_BOLD,
            fontSize=_Q_FONT_SIZE,
            leading=_LEADING,
        ),
    }
    return _CACHED_STYLES


# ---------------------------------------------------------------------------
# Characters
# ---------------------------------------------------------------------------
OMR_CIRCLE = '\u25CB'     # ◯
FILLED_CIRCLE = '\u25CF'  # ●
BENGALI_PREFIXES = ['ক)', 'খ)', 'গ)', 'ঘ)']

# Cached TableStyle objects (avoid recreating for every question)
_OPT_TABLE_STYLE = TableStyle([
    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ('LEFTPADDING', (0, 0), (-1, -1), 0),
    ('RIGHTPADDING', (0, 0), (-1, -1), 2),
    ('TOPPADDING', (0, 0), (-1, -1), 0),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
])

_CELL_TABLE_STYLE = TableStyle([
    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ('LEFTPADDING', (0, 0), (-1, -1), 0),
    ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ('TOPPADDING', (0, 0), (-1, -1), 0),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
])

_HEADER_TABLE_STYLE = TableStyle([
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('LEFTPADDING', (0, 0), (-1, -1), 0),
    ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ('TOPPADDING', (0, 0), (-1, -1), 0),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
])

_MAIN_TABLE_STYLE = TableStyle([
    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ('LEFTPADDING', (0, 0), (0, 0), 0),
    ('RIGHTPADDING', (0, 0), (0, 0), _COLUMN_GAP / 2),
    ('LEFTPADDING', (1, 0), (1, 0), _COLUMN_GAP / 2),
    ('RIGHTPADDING', (1, 0), (1, 0), 0),
    ('TOPPADDING', (0, 0), (-1, -1), 0),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
])


def _escape(text: str) -> str:
    """Escape XML entities for ReportLab Paragraph markup."""
    return (
        text
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
    )


def _escape_and_format_math(text: str) -> str:
    """Escape text and format math expressions for ReportLab.
    
    Order matters: first escape, then add ReportLab tags for math.
    """
    if not text:
        return text
    
    # First escape XML entities
    result = _escape(text)
    
    # Then apply math formatting (add <super>/<sub> tags)
    result = _format_math_text(result)
    
    return result


# ---------------------------------------------------------------------------
# Question Builders
# ---------------------------------------------------------------------------
def _build_question_flowable(text: str, style: ParagraphStyle, prefix: str = '') -> Flowable:
    """Build a flowable for text with inline math formatting.
    
    Uses _escape_and_format_math to handle fractions, superscripts, and subscripts
    within a single Paragraph to maintain proper text flow.
    """
    formatted = _escape_and_format_math(text)
    full_text = f'{prefix}{formatted}' if prefix else formatted
    return Paragraph(full_text, style)


def _build_question_cell(q: dict, show_answer: bool, styles: dict, omr_style: bool = True) -> list:
    """Build flowables for one question (for use in a table cell).
    
    Uses inline math formatting to keep fractions and superscripts within
    continuous text flow without breaking lines.
    """
    flowables = []

    q_text = q.get('question_text', '')
    q_id = _escape(str(q.get('id', '')))

    # Question text - use inline math formatting for proper text flow
    formatted_text = _escape_and_format_math(q_text)
    flowables.append(Paragraph(f'{q_id}. {formatted_text}', styles['question']))

    # Complex question sub-options
    if q.get('type') == 'complex':
        for sub_opt in q.get('sub_options', []):
            flowables.append(_build_question_flowable(sub_opt, styles['sub_option'], prefix='. '))
        prompt = q.get('final_prompt', 'নিচের কোনটি সঠিক?')
        flowables.append(_build_question_flowable(prompt, styles['prompt']))

    # Answer options (2x2 table)
    options = q.get('answer_options', [])
    correct_ans = str(q.get('correct_answer', '')).strip()

    if len(options) >= 4:
        opt_cell_width = (_COL_WIDTH - 4) / 2
        rows = []
        for row_idx in range(2):
            row = []
            for col_idx in range(2):
                opt_idx = row_idx * 2 + col_idx
                opt_text = str(options[opt_idx]).strip()
                is_correct = show_answer and opt_text == correct_ans
                prefix = BENGALI_PREFIXES[opt_idx]
                style = styles['option_bold'] if is_correct else styles['option_normal']
                # Use OptionFlowable which now supports fractions
                cell = OptionFlowable(prefix, opt_text, style, filled=is_correct, omr_style=omr_style)
                row.append(cell)
            rows.append(row)

        opt_table = Table(rows, colWidths=[opt_cell_width, opt_cell_width])
        opt_table.setStyle(_OPT_TABLE_STYLE)
        flowables.append(opt_table)
    else:
        for j, opt in enumerate(options):
            is_correct = show_answer and str(opt).strip() == correct_ans
            prefix = BENGALI_PREFIXES[j] if j < len(BENGALI_PREFIXES) else ''
            style = styles['option_bold'] if is_correct else styles['option_normal']
            flowables.append(OptionFlowable(prefix, str(opt), style, filled=is_correct, omr_style=omr_style))

    return flowables


class OptionFlowable(Flowable):
    """Flowable that draws an OMR-style circle and renders the option text next to it.

    Supports inline fractions and math expressions using inline formatting.
    """
    __slots__ = ('prefix', 'text', 'style', 'filled', 'circle_dia', 'content_flowable', 'width', 'height', 'omr_style')

    def __init__(self, prefix: str, text: str, style: ParagraphStyle, filled: bool = False, circle_dia: int = 8, omr_style: bool = True):
        super().__init__()
        self.prefix = prefix
        self.text = text  # Store unescaped, process in wrap
        self.style = style
        self.filled = filled
        self.circle_dia = circle_dia
        self.omr_style = omr_style
        self.content_flowable = None  # Lazy creation

    def wrap(self, availWidth, availHeight):
        # Create content flowable lazily with inline math formatting
        if self.content_flowable is None:
            formatted = _escape_and_format_math(self.text)
            self.content_flowable = Paragraph(f'{self.prefix} {formatted}', self.style)
        
        if self.omr_style:
            gap = 4
            text_avail = max(availWidth - (self.circle_dia + gap), 10)
        else:
            text_avail = max(availWidth, 10)
        _, h = self.content_flowable.wrap(text_avail, availHeight)
        self.width = availWidth
        self.height = max(h, self.circle_dia) if self.omr_style else h
        return (self.width, self.height)

    def draw(self):
        c = self.canv
        if self.omr_style:
            radius = self.circle_dia / 2.0
            x = radius
            y = self.height / 2.0
            c.saveState()
            c.setLineWidth(0.8)
            c.setStrokeColor(colors.black)
            c.setFillColor(colors.black if self.filled else colors.white)
            c.circle(x, y, radius, stroke=1, fill=1)
            # Draw content flowable
            self.content_flowable.drawOn(c, self.circle_dia + 4, 0)
            c.restoreState()
        else:
            self.content_flowable.drawOn(c, 0, 0)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def create_question_paper_pdf(
    questions: list,
    output_path: Optional[str],
    paper_config: dict,
    show_answer: bool = False,
    omr_style: bool = True,
    sq_config: dict = None,
    cq_config: dict = None,
) -> Union[io.BytesIO, str]:
    """
    Generate a two-column MCQ question paper as PDF.
    Also renders SQ (خ-বিভাগ) and CQ (গ-বিভাগ) sections when sq_config / cq_config provided.
    """
    logger.debug(f"create_question_paper_pdf called with {len(questions)} questions")
    
    # 1) Prefer LibreOffice/soffice DOCX -> PDF conversion if available.
    #    This preserves DOCX output exactly and ensures correct Bengali shaping.
    soffice_path = shutil.which('soffice') or shutil.which('libreoffice')
    if soffice_path:
        logger.info(f"Using LibreOffice at {soffice_path} for PDF generation")
        tmpdir = tempfile.mkdtemp(prefix='prosno_docx2pdf_')
        try:
            docx_path = os.path.join(tmpdir, 'paper.docx')
            pdf_path = os.path.join(tmpdir, 'paper.pdf')
            # Create DOCX using the existing document generator
            from . import document_generator as _docgen
            _docgen.create_question_paper(
                questions, docx_path, paper_config,
                show_answer=show_answer, omr_style=omr_style,
                sq_config=sq_config, cq_config=cq_config,
            )

            # Run headless conversion
            cmd = [soffice_path, '--headless', '--convert-to', 'pdf', '--outdir', tmpdir, docx_path]
            result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.debug(f"soffice conversion completed: {result.returncode}")

            # Read generated PDF
            with open(pdf_path, 'rb') as f:
                data = f.read()

            if output_path is None:
                buf = io.BytesIO(data)
                buf.seek(0)
                return buf
            else:
                out_dir = os.path.dirname(output_path)
                if out_dir and not os.path.exists(out_dir):
                    os.makedirs(out_dir)
                with open(output_path, 'wb') as out_f:
                    out_f.write(data)
                return output_path
        except Exception as e:
            logger.error(f"LibreOffice conversion failed: {e}")
            # Fall through to try other methods
        finally:
            try:
                shutil.rmtree(tmpdir)
            except Exception:
                pass

    # 2) Prefer WeasyPrint (HTML -> PDF) if available (better complex-script shaping)
    try:
        from weasyprint import HTML, CSS  # type: ignore
        weasy_ok = True
        logger.info("WeasyPrint available, using for PDF generation")
    except Exception as e:
        weasy_ok = False
        logger.debug(f"WeasyPrint not available: {e}")

    if weasy_ok:
        try:
            # WeasyPrint path: generate DOCX via document_generator first, then
            # convert with LibreOffice if available, else fall through to ReportLab.
            # For now, fall through so ReportLab handles CQ/SQ rendering below.
            html = _build_html(questions, paper_config, show_answer, omr_style=omr_style)
            # If output_path is None, return BytesIO buffer
            if output_path is None:
                from weasyprint import HTML
                pdf_bytes = HTML(string=html).write_pdf(stylesheets=None)
                buf = io.BytesIO(pdf_bytes)
                buf.seek(0)
                return buf
            else:
                # Ensure output dir exists
                out_dir = os.path.dirname(output_path)
                if out_dir and not os.path.exists(out_dir):
                    os.makedirs(out_dir)
                HTML(string=html).write_pdf(output_path)
                return output_path
        except Exception as e:
            logger.error(f"WeasyPrint PDF generation failed: {e}")
            # Fall through to ReportLab

    # 3) Fallback to ReportLab renderer (best-effort)
    logger.info("Using ReportLab for PDF generation (fallback)")
    _register_fonts()
    styles = _build_styles()

    # Output target
    buffer: Optional[io.BytesIO] = None
    if output_path is None:
        buffer = io.BytesIO()
        target = buffer
    else:
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        target = output_path

    doc = SimpleDocTemplate(
        target,
        pagesize=A4,
        leftMargin=_LEFT_MARGIN,
        rightMargin=_RIGHT_MARGIN,
        topMargin=_TOP_MARGIN,
        bottomMargin=_BOTTOM_MARGIN,
    )

    story = []

    # --- Header section ---
    title = paper_config.get('title', 'Home Test')
    story.append(Paragraph(_escape(title), styles['title']))

    class_name = paper_config.get('class_name', '')
    subject_name = paper_config.get('subject_name', '')
    if class_name:
        story.append(Paragraph(_escape(class_name), styles['center']))
    if subject_name:
        story.append(Paragraph(f'বিষয়: {_escape(subject_name)}', styles['center']))

    # Time & marks row
    num_questions = len(questions)
    time_minutes = paper_config.get('time', num_questions)
    total_marks = paper_config.get('marks', num_questions)
    bengali_time = to_bengali_numeral(time_minutes)
    bengali_marks = to_bengali_numeral(total_marks)

    time_para = Paragraph(f'সময়— {bengali_time} মিনিট', styles['header_left'])
    marks_para = Paragraph(f'পূর্ণমান— {bengali_marks}', styles['header_right'])

    header_table = Table(
        [[time_para, marks_para]],
        colWidths=[_USABLE_WIDTH / 2, _USABLE_WIDTH / 2],
    )
    header_table.setStyle(_HEADER_TABLE_STYLE)
    story.append(header_table)
    story.append(Spacer(1, 8))

    # --- Two-column questions table ---
    # Split questions into left and right columns
    n = len(questions)
    mid = (n + 1) // 2  # Left column gets the extra if odd
    left_questions = questions[:mid]
    right_questions = questions[mid:]

    # Build cell content for each column
    left_cell_content = []
    for q in left_questions:
        left_cell_content.extend(_build_question_cell(q, show_answer, styles, omr_style=omr_style))

    right_cell_content = []
    for q in right_questions:
        right_cell_content.extend(_build_question_cell(q, show_answer, styles, omr_style=omr_style))

    # Create two-column table
    # Each cell contains a nested table with the questions
    def wrap_in_table(flowables):
        """Wrap flowables in a single-cell table for proper rendering."""
        if not flowables:
            return Paragraph('', styles['option_normal'])
        rows = [[f] for f in flowables]
        t = Table(rows, colWidths=[_COL_WIDTH])
        t.setStyle(_CELL_TABLE_STYLE)
        return t

    left_table = wrap_in_table(left_cell_content)
    right_table = wrap_in_table(right_cell_content)

    # Main two-column table
    main_table = Table(
        [[left_table, right_table]],
        colWidths=[_COL_WIDTH, _COL_WIDTH],
        hAlign='LEFT',
    )
    main_table.setStyle(_MAIN_TABLE_STYLE)

    story.append(main_table)

    # --- Short Question section (খ-বিভাগ) ---
    if sq_config and sq_config.get('questions'):
        sq_questions = sq_config['questions']
        sq_answer_count = sq_config.get('answer_count', len(sq_questions))
        sq_marks = sq_config.get('marks_per_question', 2)
        bn_n = to_bengali_numeral(sq_answer_count)
        bn_marks = to_bengali_numeral(sq_marks)

        story.append(Spacer(1, 10))
        story.append(Paragraph('খ-বিভাগ (সংক্ষিপ্ত প্রশ্ন)', styles['title']))
        story.append(Paragraph(
            f'নিচের যেকোনো {bn_n}টির উত্তর দাও। প্রতিটি প্রশ্নের মান {bn_marks}।',
            styles['center']
        ))
        story.append(Spacer(1, 6))

        sq_style = ParagraphStyle(
            'SQQuestion', fontName=FONT_REGULAR, fontSize=9, leading=12, spaceBefore=3, spaceAfter=2
        )
        sq_mark_style = ParagraphStyle(
            'SQMark', fontName=FONT_BOLD, fontSize=9, leading=12, alignment=TA_RIGHT
        )
        for sq_idx, sq_q in enumerate(sq_questions, 1):
            q_text = sq_q.get('question_text', '')
            q_marks = sq_q.get('marks', sq_marks)
            bn_idx = to_bengali_numeral(sq_idx)
            bn_q_marks = to_bengali_numeral(q_marks)
            formatted = _escape_and_format_math(q_text)
            row = [
                Paragraph(f'{bn_idx}। {formatted}', sq_style),
                Paragraph(bn_q_marks, sq_mark_style),
            ]
            sq_row_table = Table([row], colWidths=[_USABLE_WIDTH - 40, 40])
            sq_row_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]))
            story.append(sq_row_table)

    # --- Creative Question section (গ-বিভাগ) ---
    if cq_config and cq_config.get('questions'):
        cq_questions = cq_config['questions']
        cq_answer_count = cq_config.get('answer_count', len(cq_questions))
        bn_n = to_bengali_numeral(cq_answer_count)

        story.append(Spacer(1, 10))
        story.append(Paragraph('গ-বিভাগ (সৃজনশীল প্রশ্ন)', styles['title']))
        story.append(Paragraph(f'নিচের যেকোনো {bn_n}টির উত্তর দাও।', styles['center']))
        story.append(Spacer(1, 6))

        stem_style = ParagraphStyle(
            'CQStem', fontName=FONT_BOLD, fontSize=9, leading=12,
            spaceBefore=8, spaceAfter=2, backColor=colors.HexColor('#F2F2F2')
        )
        part_style = ParagraphStyle(
            'CQPart', fontName=FONT_REGULAR, fontSize=9, leading=12,
            leftIndent=18, spaceAfter=2
        )
        cq_mark_style = ParagraphStyle(
            'CQMark', fontName=FONT_BOLD, fontSize=9, leading=12, alignment=TA_RIGHT
        )

        cq_bengali_parts = [
            ('part_ka', 'marks_ka', 'ক'),
            ('part_kha', 'marks_kha', 'খ'),
            ('part_ga', 'marks_ga', 'গ'),
            ('part_gha', 'marks_gha', 'ঘ'),
        ]
        for cq_idx, cq_q in enumerate(cq_questions, 1):
            bn_idx = to_bengali_numeral(cq_idx)
            stem = _escape_and_format_math(cq_q.get('stem', ''))
            story.append(Paragraph(f'{bn_idx}। উদ্দীপক: {stem}', stem_style))

            for part_key, marks_key, label in cq_bengali_parts:
                part_text = cq_q.get(part_key)
                if not part_text:
                    continue
                part_marks = cq_q.get(marks_key, 0)
                bn_part_marks = to_bengali_numeral(part_marks)
                formatted_part = _escape_and_format_math(part_text)
                row = [
                    Paragraph(f'{label}. {formatted_part}', part_style),
                    Paragraph(bn_part_marks, cq_mark_style),
                ]
                cq_row_table = Table([row], colWidths=[_USABLE_WIDTH - 40, 40])
                cq_row_table.setStyle(TableStyle([
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 0),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                    ('TOPPADDING', (0, 0), (-1, -1), 0),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ]))
                story.append(cq_row_table)

    # Build PDF
    doc.build(story)

    if output_path is None and buffer is not None:
        buffer.seek(0)
        return buffer
    return output_path or ''


def generate_paper_to_memory_pdf(
    questions: list,
    paper_config: dict,
    student_only: bool = False,
    teacher_only: bool = False,
    omr_style: bool = True,
    sq_config: dict = None,
    cq_config: dict = None,
) -> tuple:
    """Generate PDF copies as BytesIO buffers.
    
    Args:
        questions: List of question objects or dicts
        paper_config: Paper configuration dict
        student_only: If True, only generate student version (teacher_buffer will be None)
        teacher_only: If True, only generate teacher version (student_buffer will be None)
        sq_config: Optional short question section config (keys: questions, answer_count, marks_per_question)
        cq_config: Optional creative question section config (keys: questions, answer_count)
    
    Returns:
        Tuple of (student_buffer, teacher_buffer). One may be None if only generating one version.
    """
    question_list = _prepare_question_list(questions)
    
    student_buffer = None
    teacher_buffer = None
    
    if not teacher_only:
        student_buffer = create_question_paper_pdf(
            question_list, None, paper_config, show_answer=False, omr_style=omr_style,
            sq_config=sq_config, cq_config=cq_config,
        )
    
    if not student_only:
        teacher_buffer = create_question_paper_pdf(
            question_list, None, paper_config, show_answer=True, omr_style=True,
            sq_config=sq_config, cq_config=cq_config,
        )
    
    # Free up memory after PDF generation (important for low-memory environments)
    del question_list
    _clear_math_cache()
    _cleanup_memory()
    
    return student_buffer, teacher_buffer


def generate_paper_from_db_pdf(
    questions: list,
    paper_config: dict,
    output_folder: str,
    omr_style: bool = True,
    sq_config: dict = None,
    cq_config: dict = None,
) -> tuple:
    """Generate both student and teacher PDF copies saved to disk."""
    import uuid as _uuid
    from datetime import datetime as _dt

    question_list = _prepare_question_list(questions)

    timestamp = _dt.now().strftime('%Y%m%d_%H%M%S')
    unique_id = str(_uuid.uuid4())[:8]
    base = f"question_paper_{timestamp}_{unique_id}"

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    student_path = os.path.join(output_folder, f"{base}_student.pdf")
    create_question_paper_pdf(
        question_list, student_path, paper_config, show_answer=False, omr_style=omr_style,
        sq_config=sq_config, cq_config=cq_config,
    )

    teacher_path = os.path.join(output_folder, f"{base}_teacher.pdf")
    create_question_paper_pdf(
        question_list, teacher_path, paper_config, show_answer=True, omr_style=True,
        sq_config=sq_config, cq_config=cq_config,
    )

    # Free up memory after PDF generation
    del question_list
    _clear_math_cache()
    _cleanup_memory()

    return student_path, teacher_path


def _prepare_question_list(questions: list) -> list:
    """Convert Question model objects to dicts with sequential IDs."""
    question_list = []
    for idx, q in enumerate(questions, 1):
        if hasattr(q, 'to_dict'):
            q_dict = q.to_dict()
        else:
            q_dict = q.copy() if isinstance(q, dict) else q
        q_dict['id'] = str(idx)
        question_list.append(q_dict)
    return question_list
