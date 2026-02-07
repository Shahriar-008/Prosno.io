#!/usr/bin/env python3
import os
import sys
from app.utils.pdf_generator import create_question_paper_pdf

questions = [
    {
        'id': '1',
        'question_text': 'উপরের কোনটি সঠিক বলে মনে করেন?',
        'answer_options': ['বিকল্প A', 'বিকল্প B', 'বিকল্প C', 'বিকল্প D'],
        'correct_answer': 'বিকল্প B',
    },
    {
        'id': '2',
        'question_text': 'বীজগণিতের একটি সহজ প্রশ্ন: ২+২ = ?',
        'answer_options': ['১', '২', '৪', '৬'],
        'correct_answer': '৪',
    },
    {
        'id': '3',
        'question_text': 'বাংলা ভাষার একটি প্রশ্ন: শব্দের প্রথম অংশ কী?',
        'answer_options': ['অংশ ক', 'অংশ খ', 'অংশ গ', 'অংশ ঘ'],
        'correct_answer': 'অংশ ক',
    }
]

paper_config = {
    'title': 'পরীক্ষা - নমুনা পেপার (Docker Test)',
    'class_name': 'শ্রেণি: ৫',
    'subject_name': 'বিষয়: গণিত',
    'time': 30,
    'marks': 20,
}

def main():
    out = sys.argv[1] if len(sys.argv) > 1 else '/tmp/test_paper_docker.pdf'
    print('Generating PDF to', out)
    create_question_paper_pdf(questions, out, paper_config, show_answer=False)
    if os.path.exists(out):
        print('Done. Size:', os.path.getsize(out))
    else:
        print('No output produced.')

if __name__ == '__main__':
    main()
