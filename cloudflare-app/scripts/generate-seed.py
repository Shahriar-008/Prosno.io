#!/usr/bin/env python3
"""Generate cloudflare-app/migrations/0002_seed_nctb.sql from ../seed_nctb.py."""
import json
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT_DIR)

from seed_nctb import NCTB_DATA  # noqa: E402

OUT_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "migrations", "0002_seed_nctb.sql")
)


def sql_str(val):
    if val is None:
        return "NULL"
    return "'" + str(val).replace("'", "''") + "'"


def main():
    lines = [
        "-- Prosno.io D1 Seed Migration (0002_seed_nctb.sql)",
        "-- Generated from seed_nctb.py + rich Bangla sample questions",
        "",
    ]

    class_id = 0
    subject_id = 0
    chapter_id = 0

    science_ch5_id = None
    math_subject_id = None
    math_ch1_id = None
    science_subject_id = None

    for class_num in sorted(NCTB_DATA.keys()):
        cdata = NCTB_DATA[class_num]
        class_id += 1
        lines.append(
            f"INSERT OR IGNORE INTO classes (id, name, name_bn, level, \"order\", is_active) "
            f"VALUES ({class_id}, {sql_str(cdata['name'])}, {sql_str(cdata['name_bn'])}, "
            f"{sql_str(cdata['level'])}, {class_num}, 1);"
        )

        for subj_order, (subj_name, sdata) in enumerate(cdata["subjects"].items(), start=1):
            subject_id += 1
            lines.append(
                f"INSERT OR IGNORE INTO subjects (id, name, name_bn, class_id, \"order\", is_active) "
                f"VALUES ({subject_id}, {sql_str(subj_name)}, {sql_str(sdata['name_bn'])}, "
                f"{class_id}, {subj_order}, 1);"
            )
            if class_num in (9, 10) and ("Science" in subj_name or "বিজ্ঞান" in sdata["name_bn"]) and science_subject_id is None:
                science_subject_id = subject_id
            if class_num in (9, 10) and ("Math" in subj_name or "গণিত" in sdata["name_bn"]) and math_subject_id is None:
                math_subject_id = subject_id

            for chap_order, (chap_bn, chap_en) in enumerate(sdata["chapters"], start=1):
                chapter_id += 1
                lines.append(
                    f"INSERT OR IGNORE INTO chapters (id, name, name_bn, chapter_number, subject_id, \"order\", is_active) "
                    f"VALUES ({chapter_id}, {sql_str(chap_en)}, {sql_str(chap_bn)}, "
                    f"{chap_order}, {subject_id}, {chap_order}, 1);"
                )
                if science_subject_id == subject_id and chap_order == 5 and science_ch5_id is None:
                    science_ch5_id = chapter_id
                if math_subject_id == subject_id and chap_order == 1 and math_ch1_id is None:
                    math_ch1_id = chapter_id

    # Fallback IDs if specific chapters weren't matched
    if science_ch5_id is None:
        science_ch5_id = 1
    if math_ch1_id is None:
        math_ch1_id = min(2, chapter_id)
    if science_subject_id is None:
        science_subject_id = 1
    if math_subject_id is None:
        math_subject_id = min(2, subject_id)

    lines.append("")
    lines.append("-- Sample Rich Bangla MCQs (with Board/Year, Explanations, Math & Complex Types)")

    sample_mcqs = [
        (
            "চোখের কোন অংশ ক্যামেরার ডায়াফ্রামের মতো কাজ করে?",
            "simple", None, None,
            ["রেটিনা", "আইরিশ", "কর্নিয়া", "অক্ষিগোলক"],
            "আইরিশ",
            "আইরিশ পিউপিলের আকার পরিবর্তন করে আলো নিয়ন্ত্রণ করে, যা ক্যামেরার ডায়াফ্রামের অনুরূপ।",
            "ঢা. বো.", 2020, science_ch5_id, "easy"
        ),
        (
            "সাধারণ চোখের স্পষ্ট দর্শনের নিকটতম দূরত্ব কত?",
            "simple", None, None,
            ["15 cm", "20 cm", "25 cm", "50 cm"],
            "25 cm",
            "একজন স্বাভাবিক পূর্ণবয়স্ক মানুষের চোখের স্পষ্ট দর্শনের নিকটতম দূরত্ব ২৫ সেমি।",
            "রা. বো.", 2023, science_ch5_id, "easy"
        ),
        (
            "লেন্সের ক্ষমতার আন্তর্জাতিক (SI) একক কোনটি?",
            "simple", None, None,
            ["ডায়প্টার (D)", "মিটার (m)", "রেডিয়ান", "ওয়াট"],
            "ডায়প্টার (D)",
            "লেন্সের ক্ষমতার প্রচলিত ও এসআই আন্তর্জাতিক একক হলো ডায়প্টার ($m^{-1}$)।",
            "য. বো.", 2021, science_ch5_id, "easy"
        ),
        (
            "রেটিনার ওপর সৃষ্ট প্রতিবিম্বের প্রকৃতি কীরূপ?",
            "simple", None, None,
            ["সোজা ও বাস্তব", "উল্টো ও বাস্তব", "সোজা ও অবাস্তব", "উল্টো ও অবাস্তব"],
            "উল্টো ও বাস্তব",
            "চোখের উত্তল লেন্স রেটিনার ওপর বাস্তব এবং উল্টো প্রতিবিম্ব তৈরি করে; মস্তিষ্ক তা সোজা করে নেয়।",
            "কু. বো.", 2022, science_ch5_id, "medium"
        ),
        (
            "ক্ষীণদৃষ্টি বা হ্রস্বদৃষ্টি (Myopia) দূর করার জন্য কোন লেন্সের চশমা ব্যবহৃত হয়?",
            "simple", None, None,
            ["উত্তল লেন্স", "অবতল লেন্স", "বেলনাকার লেন্স", "বাইফোকাল লেন্স"],
            "অবতল লেন্স",
            "ক্ষীণদৃষ্টিতে অভিসারী ক্ষমতা বেড়ে যায়, অপসারী অবতল লেন্সের মাধ্যমে আলো অপসারিত করে রেটিনায় ফেলা হয়।",
            "চ. বো.", 2020, science_ch5_id, "medium"
        ),
        (
            "একটি লেন্সের ফোকাস দূরত্ব +০.৫ মিটার হলে এর ক্ষমতা কত?",
            "simple", None, None,
            ["-২ D", "+০.৫ D", "+১ D", "+২ D"],
            "+২ D",
            "ক্ষমতা $P = \\frac{1}{f} = \\frac{1}{+0.5} = +2\\text{ D}$ (উত্তল লেন্স)।",
            "সি. বো.", 2022, science_ch5_id, "medium"
        ),
        (
            "কম আলোতে দর্শনের জন্য রেটিনার কোন কোষগুলো সংবেদনশীল?",
            "simple", None, None,
            ["কোণ কোষ", "রড কোষ", "অন্ধবিন্দু", "পীতবিন্দু"],
            "রড কোষ",
            "রড কোষ অনুজ্জ্বল ও মৃদু আলোতে দেখতে সহায়তা করে (রডোপসিন প্রোটিন সমৃদ্ধ)।",
            "ব. বো.", 2019, science_ch5_id, "medium"
        ),
        (
            "অপটিক্যাল ফাইবারে আলোর কোন ঘটনাটি সংঘটিত হয়?",
            "simple", None, None,
            ["নিয়মিত প্রতিফলন", "পূর্ণ অভ্যন্তরীণ প্রতিফলন", "অপবর্তন", "বিচ্ছুরণ"],
            "পূর্ণ অভ্যন্তরীণ প্রতিফলন",
            "অপটিক্যাল ফাইবারে অভ্যন্তরীণ প্রতিফলন কাজে লাগিয়ে দ্রুত আলোক সংকেত পাঠানো হয়।",
            "ঢা. বো.", 2019, science_ch5_id, "easy"
        ),
        (
            "একটি চশমার ক্ষমতা +৩.০ D হলে এর ফোকাস দূরত্ব কত?",
            "simple", None, None,
            ["+০.৩৩ মিটার", "+৩.০ মিটার", "-০.৩৩ মিটার", "+১.৫ মিটার"],
            "+০.৩৩ মিটার",
            "$f = \\frac{1}{P} = \\frac{1}{+3.0} = +0.33\\text{ m}$ (৩৩.৩৩ সেমি)।",
            "ব. বো.", 2021, science_ch5_id, "medium"
        ),
        (
            "পূর্ণ অভ্যন্তরীণ প্রতিফলনের জন্য প্রযোজ্য—",
            "complex",
            ["i. আলো ঘন মাধ্যম থেকে হালকা মাধ্যমে যাবে", "ii. আপতন কোণ সংকট কোণের চেয়ে বড় হবে", "iii. প্রতিসরণ কোণ ৯০° হবে"],
            "নিচের কোনটি সঠিক?",
            ["i ও ii", "i ও iii", "ii ও iii", "i, ii ও iii"],
            "i ও ii",
            "পূর্ণ অভ্যন্তরীণ প্রতিফলনের দুটি শর্ত: আলো ঘন থেকে হালকা মাধ্যমে যাবে এবং আপতন কোণ সংকট কোণের চেয়ে বড় হবে।",
            "ঢা. বো.", 2023, science_ch5_id, "hard"
        ),
        (
            "আলোর প্রতিসরণের সময় কোনটি অপরিবর্তিত থাকে?",
            "simple", None, None,
            ["বেগ", "তরঙ্গদৈর্ঘ্য", "কম্পাঙ্ক", "দিক"],
            "কম্পাঙ্ক",
            "প্রতিসরণের সময় আলোর বেগ ও তরঙ্গদৈর্ঘ্য পরিবর্তিত হলেও উৎসের ওপর নির্ভরশীল কম্পাঙ্ক অপরিবর্তিত থাকে।",
            "রা. বো.", 2019, science_ch5_id, "medium"
        ),
        (
            "কোন ভিটামিনের অভাবে চোখে রাতকানা রোগ সৃষ্টি হয়?",
            "simple", None, None,
            ["ভিটামিন বি", "ভিটামিন সি", "ভিটামিন এ", "ভিটামিন ডি"],
            "ভিটামিন এ",
            "রেটিনার রড কোষের রডোপসিন গঠনে ভিটামিন এ অপরিহার্য; এর অভাবে রাতকানা হয়।",
            "য. বো.", 2019, science_ch5_id, "easy"
        ),
        (
            "যদি $x + \\frac{1}{x} = 3$ হয়, তবে $x^2 + \\frac{1}{x^2}$ এর মান কত?",
            "simple", None, None,
            ["7", "9", "11", "5"],
            "7",
            "$x^2 + \\frac{1}{x^2} = (x + \\frac{1}{x})^2 - 2 = 3^2 - 2 = 7$।",
            "ঢা. বো.", 2023, math_ch1_id, "medium"
        ),
        (
            "যদি $a + b = 5$ এবং $ab = 4$ হয়, তবে $(a - b)^2$ এর মান কত?",
            "simple", None, None,
            ["9", "16", "21", "41"],
            "9",
            "$(a - b)^2 = (a + b)^2 - 4ab = 5^2 - 4(4) = 25 - 16 = 9$।",
            "রা. বো.", 2022, math_ch1_id, "easy"
        ),
        (
            "বাস্তব সংখ্যার ক্ষেত্রে নিচের বিবৃতিগুলো লক্ষ কর:",
            "complex",
            ["i. সকল মূলদ সংখ্যাই বাস্তব সংখ্যা", "ii. $\\sqrt{2}$ একটি অমূলদ সংখ্যা", "iii. শূন্য একটি ধনাত্মক সংখ্যা"],
            "নিচের কোনটি সঠিক?",
            ["i ও ii", "i ও iii", "ii ও iii", "i, ii ও iii"],
            "i ও ii",
            "শূন্য ধনাত্মক বা ঋণাত্মক কোনোটিই নয়; তবে সকল মূলদ সংখ্যা ও $\\sqrt{2}$ বাস্তব সংখ্যা।",
            "চ. বো.", 2023, math_ch1_id, "hard"
        ),
        (
            "a² - b² এর উৎপাদক কোনটি?",
            "simple", None, None,
            ["(a+b)(a-b)", "(a+b)²", "(a-b)²", "a²+2ab+b²"],
            "(a+b)(a-b)",
            "বীজগাণিতিক অভেদ অনুযায়ী $a^2 - b^2 = (a + b)(a - b)$।",
            "সি. বো.", 2021, math_ch1_id, "easy"
        ),
        (
            "কোনো সেটের উপাদান সংখ্যা 3 হলে, এর উপসেট সংখ্যা কত?",
            "simple", None, None,
            ["3", "6", "8", "9"],
            "8",
            "উপাদান সংখ্যা $n = 3$ হলে উপসেট সংখ্যা $2^n = 2^3 = 8$।",
            "কু. বো.", 2023, math_ch1_id, "easy"
        ),
        (
            "ত্রিভুজের তিন কোণের সমষ্টি কত ডিগ্রি?",
            "simple", None, None,
            ["90°", "180°", "270°", "360°"],
            "180°",
            "ইউক্লিডীয় জ্যামিতিতে যেকোনো ত্রিভুজের তিন কোণের সমষ্টি দুই সমকোণ বা $180^\\circ$।",
            "ব. বো.", 2020, math_ch1_id, "easy"
        ),
        (
            "(1/x) + (1/y) এর সরলকৃত মান কোনটি?",
            "simple", None, None,
            ["(x+y)/(xy)", "xy/(x+y)", "2/(x+y)", "1/(xy)"],
            "(x+y)/(xy)",
            "ভগ্নাংশের যোগফল: $\\frac{1}{x} + \\frac{1}{y} = \\frac{x+y}{xy}$।",
            "য. বো.", 2022, math_ch1_id, "medium"
        ),
        (
            "পানি থেকে আলো বাতাসে প্রবেশের সময় সংকট কোণ প্রায় কত?",
            "simple", None, None,
            ["24°", "42°", "49°", "90°"],
            "49°",
            "পানি ও বায়ুর জন্য সংকট কোণের মান $48.6^\\circ$ বা প্রায় $49^\\circ$।",
            "দি. বো.", 2018, science_ch5_id, "medium"
        ),
    ]

    for idx, (qtext, qtype, sub_opts, fprompt, opts, ans, expl, board, year, ch_id, diff) in enumerate(sample_mcqs, 1):
        sub_sql = sql_str(json.dumps(sub_opts, ensure_ascii=False)) if sub_opts is not None else "NULL"
        fp_sql = sql_str(fprompt) if fprompt is not None else "NULL"
        opts_sql = sql_str(json.dumps(opts, ensure_ascii=False))
        lines.append(
            f"INSERT OR IGNORE INTO questions "
            f"(id, question_text, question_type, sub_options, final_prompt, answer_options, correct_answer, explanation, board, year, chapter_id, difficulty, marks, is_active) "
            f"VALUES ({idx}, {sql_str(qtext)}, {sql_str(qtype)}, {sub_sql}, {fp_sql}, {opts_sql}, {sql_str(ans)}, {sql_str(expl)}, {sql_str(board)}, {year}, {ch_id}, {sql_str(diff)}, 1, 1);"
        )

    lines.append("")
    lines.append("-- Sample Short Questions (খ-বিভাগ)")
    sample_sqs = [
        (science_subject_id, science_ch5_id, "লেন্সের ক্ষমতা কাকে বলে? এর এসআই একক লেখ।", "কোনো লেন্সের অভিসারী বা অপসারী ক্ষমতার পরিমাপকে লেন্সের ক্ষমতা বলে; এর একক ডায়প্টার (D)।", 2, "ঢা. বো.", 2023),
        (science_subject_id, science_ch5_id, "ক্ষীণদৃষ্টি বা মায়োপিয়া কী এবং কীভাবে প্রতিকার করা হয়?", "কাছের বস্তু স্পষ্ট দেখলেও দূরের বস্তু ঝাপসা দেখা যায়; অবতল লেন্সের চশমা ব্যবহারে এর প্রতিকার হয়।", 2, "রা. বো.", 2022),
        (science_subject_id, science_ch5_id, "পূর্ণ অভ্যন্তরীণ প্রতিফলনের দুটি শর্ত লেখ।", "১) আলো ঘন মাধ্যম থেকে হালকা মাধ্যমে যাবে, ২) আপতন কোণ সংকট কোণের চেয়ে বড় হবে।", 2, "চ. বো.", 2021),
        (math_subject_id, math_ch1_id, "যদি $x - \\frac{1}{x} = 4$ হয়, তবে $x^2 + \\frac{1}{x^2}$ এর মান নির্ণয় কর।", "$x^2 + \\frac{1}{x^2} = (x - \\frac{1}{x})^2 + 2 = 16 + 2 = 18$", 2, "য. বো.", 2023),
        (math_subject_id, math_ch1_id, "অমূলদ সংখ্যা কাকে বলে? একটি উদাহরণ দাও।", "যে সংখ্যাকে $\\frac{p}{q}$ আকারে প্রকাশ করা যায় না, যেমন $\\sqrt{2}$।", 2, "সি. বো.", 2022),
    ]
    for idx, (s_id, c_id, qtext, ans, marks, board, year) in enumerate(sample_sqs, 1):
        lines.append(
            f"INSERT OR IGNORE INTO short_questions (id, subject_id, chapter_id, question_text, answer, marks, board, year, is_active) "
            f"VALUES ({idx}, {s_id}, {c_id}, {sql_str(qtext)}, {sql_str(ans)}, {marks}, {sql_str(board)}, {year}, 1);"
        )

    lines.append("")
    lines.append("-- Sample Creative Questions (গ-বিভাগ সৃজনশীল)")
    sample_cqs = [
        (
            science_subject_id, science_ch5_id,
            "রহিম সাহেব দূরের সাইনবোর্ড স্পষ্ট দেখতে পান না, কিন্তু কাছের বই পড়তে পারেন। অপরদিকে তার পিতা +2.5 D ক্ষমতার চশমা ব্যবহার করেন।",
            "চোখের উপযোজন কী?",
            "রহিম সাহেবের চোখের ত্রুটিটির নাম কী এবং এর কারণ ব্যাখ্যা কর।",
            "রহিম সাহেবের পিতার চশমার লেন্সের ফোকাস দূরত্ব নির্ণয় কর।",
            "রহিম সাহেব ও তার পিতার চোখের ত্রুটি প্রতিকারের উপায় রশ্মিচিত্রসহ তুলনামূলক আলোচনা কর।",
            "ঢা. বো.", 2023
        ),
        (
            science_subject_id, science_ch5_id,
            "একটি আলোক রশ্মি পানি (প্রতিসরণাঙ্ক $1.33$) থেকে বায়ুতে আপতিত হচ্ছে। পানি-বায়ু বিভেদতলে সংকট কোণ $48.6^\\circ$।",
            "সংকট কোণ কাকে বলে?",
            "আলোর প্রতিসরণের সময় কম্পাঙ্ক অপরিবর্তিত থাকে কেন?",
            "আপতন কোণ $52^\\circ$ হলে আলোক রশ্মির গতিপথ কীরূপ হবে? ব্যাখ্যা কর।",
            "পূর্ণ অভ্যন্তরীণ প্রতিফলন কীভাবে অপটিক্যাল ফাইবার ও চিকিৎসাক্ষেত্রে ব্যবহৃত হয় তা বিশ্লেষণ কর।",
            "রা. বো.", 2022
        ),
        (
            math_subject_id, math_ch1_id,
            "$A = x^2 - 5x + 1 = 0$ (যেখানে $x \\neq 0$) একটি বীজগাণিতিক সমীকরণ।",
            "উৎপাদকে বিশ্লেষণ কর: $p^2 - 9q^2$।",
            "দেখাও যে, $x + \\frac{1}{x} = 5$।",
            "$x^2 + \\frac{1}{x^2}$ এবং $x^3 + \\frac{1}{x^3}$ এর মান নির্ণয় কর।",
            "প্রমাণ কর যে, $x^4 + \\frac{1}{x^4} = 527$।",
            "কু. বো.", 2023
        ),
    ]
    for idx, (s_id, c_id, stem, ka, kha, ga, gha, board, year) in enumerate(sample_cqs, 1):
        lines.append(
            f"INSERT OR IGNORE INTO cq_questions (id, subject_id, chapter_id, stem, part_ka, part_kha, part_ga, part_gha, marks_ka, marks_kha, marks_ga, marks_gha, board, year, is_active) "
            f"VALUES ({idx}, {s_id}, {c_id}, {sql_str(stem)}, {sql_str(ka)}, {sql_str(kha)}, {sql_str(ga)}, {sql_str(gha)}, 1, 2, 3, 4, {sql_str(board)}, {year}, 1);"
        )

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Generated {OUT_PATH}: {class_id} classes, {subject_id} subjects, {chapter_id} chapters, {len(sample_mcqs)} MCQs, {len(sample_sqs)} SQs, {len(sample_cqs)} CQs")


if __name__ == "__main__":
    main()
