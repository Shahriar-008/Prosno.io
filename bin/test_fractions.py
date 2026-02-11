#!/usr/bin/env python3
"""
Test PDF generation with fractions and math expressions.

Verifies that fractions stay inline with text (no line breaking).
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.pdf_generator import create_question_paper_pdf


# Test questions with fractions (similar to the user's image)
questions = [
    {
        'id': '1',
        'question_text': '(a - b)² এর প্রথম কোনটি?',
        'answer_options': ['a² + ab + b²', 'a² + 2ab + b²', 'a² - 2ab + b²', 'a² + 2ab - b²'],
        'correct_answer': 'a² - 2ab + b²',
    },
    {
        'id': '2',
        'question_text': '(x - y)² এর মান নিচের কোনটি?',
        'answer_options': ['x² - 2xy + y²', 'x² + 2xy + y²', 'x² - xy + y²', 'x² - 2xy - y²'],
        'correct_answer': 'x² - 2xy + y²',
    },
    {
        'id': '3',
        'question_text': 'x + 1/x = 4 হলে, x² + (1/x)² এর মান কত?',
        'answer_options': ['১৪', '১৬', '১৮', '২০'],
        'correct_answer': '১৪',
    },
    {
        'id': '4',
        'question_text': 'a + b = 7 এবং ab = 10 হলে, (a - b)² এর মান কত?',
        'answer_options': ['৯', '১১', '১৩', '১৫'],
        'correct_answer': '৯',
    },
    {
        'id': '5',
        'question_text': 'গ.সা.গ (G.C.D) এর পূর্ণরূপ কী?',
        'answer_options': ['গরিষ্ঠ সাধারণ গুণক', 'গরিষ্ঠ সাধারণ গুণিতক', 'লঘিষ্ঠ সাধারণ গুণক', 'লঘিষ্ঠ সাধারণ গুণিতক'],
        'correct_answer': 'গরিষ্ঠ সাধারণ গুণক',
    },
    {
        'id': '6',
        'question_text': '12a²b এবং 18ab² এর গ.সা.গ কত?',
        'answer_options': ['6ab', '6a²b²', '36ab', '2ab'],
        'correct_answer': '6ab',
    },
    {
        'id': '7',
        'question_text': 'a + 1/a = 5 হলে, (a - 1/a)² এর মান কত?',
        'answer_options': ['২১', '২৫', '২৭', '২০'],
        'correct_answer': '২১',
    },
    {
        'id': '8',
        'question_text': '15x²y²z এবং 20x³y² এর গ.সা.গ কত?',
        'answer_options': ['5x²y²', '5xy', '15xy', '5x²y'],
        'correct_answer': '5x²y²',
    },
    {
        'id': '9',
        'question_text': 'x² + 7x + 12 এবং x² + 9x + 20 এর গ.সা.গ কত?',
        'answer_options': ['x + 3', 'x + 4', 'x + 5', 'x + 1'],
        'correct_answer': 'x + 4',
    },
    {
        'id': '10',
        'question_text': 'a + 1/a = 5 হলে, (a - 1/a)² এর মান কত?',
        'answer_options': ['২১', '২৫', '২৯', '২০'],
        'correct_answer': '২১',
    },
    {
        'id': '11',
        'question_text': 'x² - 5x + 6 এর উৎপাদক জোড়া কোনটি?',
        'answer_options': ['(x-6)(x+1)', '(x-2)(x-3)', '(x+2)(x+3)', '(x-5)(x-1)'],
        'correct_answer': '(x-2)(x-3)',
    },
    {
        'id': '12',
        'question_text': '4a² - 9b² এর উৎপাদক বিয়োজন কোনটি?',
        'answer_options': ['(2a + 3b)(2a + 3b)', '(2a - 3b)(2a - 3b)', '(2a + 3b)(2a - 3b)', '(4a + b)(4a - 3b)'],
        'correct_answer': '(2a + 3b)(2a - 3b)',
    },
]

paper_config = {
    'title': 'পরীক্ষা - গণিত (ভগ্নাংশ পরীক্ষা)',
    'class_name': 'শ্রেণি: ৮',
    'subject_name': 'বিষয়: গণিত',
    'time': 30,
    'marks': 12,
}


def main():
    """Generate test PDF with fractions."""
    out_path = sys.argv[1] if len(sys.argv) > 1 else 'output/test_fractions.pdf'
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(out_path) if os.path.dirname(out_path) else '.', exist_ok=True)
    
    print(f'Generating PDF with fractions to: {out_path}')
    create_question_paper_pdf(questions, out_path, paper_config, show_answer=False)
    
    if os.path.exists(out_path):
        print(f'Done. Size: {os.path.getsize(out_path)} bytes')
        print(f'Open the PDF to verify fractions display inline without line breaks.')
    else:
        print('Error: PDF was not generated.')
        sys.exit(1)


if __name__ == '__main__':
    main()
