#!/usr/bin/env python
"""
Seed database with NCTB Bangladesh Curriculum
Classes 1-10 with Subjects and Chapters
"""
from app import create_app, db
from app.models import Class, Subject, Chapter

# NCTB Curriculum Data
NCTB_DATA = {
    1: {
        "name": "Class 1",
        "name_bn": "১ম শ্রেণি",
        "level": "Primary",
        "subjects": {
            "Bangla": {
                "name_bn": "বাংলা",
                "chapters": [
                    ("আমার পরিবার", "My Family"),
                    ("আমার স্কুল", "My School"),
                    ("বর্ণমালা", "Alphabet"),
                    ("ছড়া ও কবিতা", "Rhymes and Poems"),
                    ("গল্প পড়ি", "Story Reading"),
                ]
            },
            "English": {
                "name_bn": "ইংরেজি",
                "chapters": [
                    ("Alphabet", "Alphabet"),
                    ("Numbers", "Numbers"),
                    ("Colors", "Colors"),
                    ("My Family", "My Family"),
                    ("Animals", "Animals"),
                ]
            },
            "Mathematics": {
                "name_bn": "গণিত",
                "chapters": [
                    ("সংখ্যা (১-১০০)", "Numbers 1-100"),
                    ("যোগ", "Addition"),
                    ("বিয়োগ", "Subtraction"),
                    ("জ্যামিতিক আকৃতি", "Geometric Shapes"),
                    ("সময়", "Time"),
                ]
            },
        }
    },
    2: {
        "name": "Class 2",
        "name_bn": "২য় শ্রেণি",
        "level": "Primary",
        "subjects": {
            "Bangla": {
                "name_bn": "বাংলা",
                "chapters": [
                    ("আমাদের দেশ", "Our Country"),
                    ("পরিবেশ পরিচিতি", "Environment Introduction"),
                    ("গদ্য পাঠ", "Prose Reading"),
                    ("পদ্য পাঠ", "Poetry Reading"),
                    ("রচনা লেখা", "Essay Writing"),
                ]
            },
            "English": {
                "name_bn": "ইংরেজি",
                "chapters": [
                    ("Greetings", "Greetings"),
                    ("My School", "My School"),
                    ("Food and Fruits", "Food and Fruits"),
                    ("Weather", "Weather"),
                    ("Simple Sentences", "Simple Sentences"),
                ]
            },
            "Mathematics": {
                "name_bn": "গণিত",
                "chapters": [
                    ("সংখ্যা (১-১০০০)", "Numbers 1-1000"),
                    ("যোগ ও বিয়োগ", "Addition and Subtraction"),
                    ("গুণ", "Multiplication"),
                    ("ভাগ", "Division"),
                    ("পরিমাপ", "Measurement"),
                ]
            },
        }
    },
    3: {
        "name": "Class 3",
        "name_bn": "৩য় শ্রেণি",
        "level": "Primary",
        "subjects": {
            "Bangla": {
                "name_bn": "বাংলা",
                "chapters": [
                    ("সুখী মানুষ", "Happy People"),
                    ("আমাদের ছোট নদী", "Our Little River"),
                    ("পাখি", "Birds"),
                    ("বাংলাদেশের মুক্তিযুদ্ধ", "Liberation War"),
                    ("ব্যাকরণ পরিচিতি", "Grammar Introduction"),
                ]
            },
            "English": {
                "name_bn": "ইংরেজি",
                "chapters": [
                    ("Going to School", "Going to School"),
                    ("In the Classroom", "In the Classroom"),
                    ("Our Environment", "Our Environment"),
                    ("Health and Hygiene", "Health and Hygiene"),
                    ("Tenses", "Tenses"),
                ]
            },
            "Mathematics": {
                "name_bn": "গণিত",
                "chapters": [
                    ("বড় সংখ্যা", "Large Numbers"),
                    ("চার অংকের যোগ-বিয়োগ", "4-digit Addition/Subtraction"),
                    ("গুণ ও ভাগ", "Multiplication and Division"),
                    ("ভগ্নাংশ পরিচিতি", "Introduction to Fractions"),
                    ("জ্যামিতি", "Geometry"),
                ]
            },
            "Bangladesh and Global Studies": {
                "name_bn": "বাংলাদেশ ও বিশ্বপরিচয়",
                "chapters": [
                    ("আমাদের বাংলাদেশ", "Our Bangladesh"),
                    ("আমাদের সমাজ", "Our Society"),
                    ("পরিবেশ", "Environment"),
                    ("জাতীয় দিবস", "National Days"),
                    ("বিশ্ব পরিচয়", "World Introduction"),
                ]
            },
            "General Science": {
                "name_bn": "প্রাথমিক বিজ্ঞান",
                "chapters": [
                    ("জীবজগৎ", "Living World"),
                    ("পরিবেশ ও প্রকৃতি", "Environment and Nature"),
                    ("আমাদের শরীর", "Our Body"),
                    ("খাদ্য ও পুষ্টি", "Food and Nutrition"),
                    ("আবহাওয়া", "Weather"),
                ]
            },
        }
    },
    4: {
        "name": "Class 4",
        "name_bn": "৪র্থ শ্রেণি",
        "level": "Primary",
        "subjects": {
            "Bangla": {
                "name_bn": "বাংলা",
                "chapters": [
                    ("বীরের রক্তে স্বাধীন এ দেশ", "Freedom with Blood"),
                    ("ফুলের বাগান", "Flower Garden"),
                    ("স্মৃতিকথা", "Memoirs"),
                    ("প্রবন্ধ", "Essays"),
                    ("ব্যাকরণ", "Grammar"),
                ]
            },
            "English": {
                "name_bn": "ইংরেজি",
                "chapters": [
                    ("Our Country", "Our Country"),
                    ("A Farmer", "A Farmer"),
                    ("Means of Transport", "Means of Transport"),
                    ("Story Time", "Story Time"),
                    ("Parts of Speech", "Parts of Speech"),
                ]
            },
            "Mathematics": {
                "name_bn": "গণিত",
                "chapters": [
                    ("বড় সংখ্যার গণনা", "Counting Large Numbers"),
                    ("গাণিতিক প্রক্রিয়া", "Mathematical Operations"),
                    ("ভগ্নাংশ", "Fractions"),
                    ("দশমিক সংখ্যা", "Decimal Numbers"),
                    ("পরিমাপ ও জ্যামিতি", "Measurement and Geometry"),
                ]
            },
            "Bangladesh and Global Studies": {
                "name_bn": "বাংলাদেশ ও বিশ্বপরিচয়",
                "chapters": [
                    ("বাংলাদেশের ইতিহাস", "History of Bangladesh"),
                    ("সামাজিক পরিবেশ", "Social Environment"),
                    ("অর্থনৈতিক পরিবেশ", "Economic Environment"),
                    ("নাগরিক জীবন", "Civic Life"),
                    ("বিশ্ব পরিচয়", "World Introduction"),
                ]
            },
            "General Science": {
                "name_bn": "প্রাথমিক বিজ্ঞান",
                "chapters": [
                    ("জীবের বৈশিষ্ট্য", "Characteristics of Living Things"),
                    ("পদার্থ ও শক্তি", "Matter and Energy"),
                    ("পরিবেশ দূষণ", "Environmental Pollution"),
                    ("স্বাস্থ্য", "Health"),
                    ("প্রযুক্তি", "Technology"),
                ]
            },
        }
    },
    5: {
        "name": "Class 5",
        "name_bn": "৫ম শ্রেণি",
        "level": "Primary",
        "subjects": {
            "Bangla": {
                "name_bn": "বাংলা",
                "chapters": [
                    ("আমার দেশ", "My Country"),
                    ("শহীদ তিতুমীর", "Shaheed Titumir"),
                    ("প্রকৃতির সৌন্দর্য", "Beauty of Nature"),
                    ("ভাষা আন্দোলন", "Language Movement"),
                    ("রচনা ও ব্যাকরণ", "Essay and Grammar"),
                ]
            },
            "English": {
                "name_bn": "ইংরেজি",
                "chapters": [
                    ("Bangladesh", "Bangladesh"),
                    ("Great People", "Great People"),
                    ("Environment", "Environment"),
                    ("Communication", "Communication"),
                    ("Composition", "Composition"),
                ]
            },
            "Mathematics": {
                "name_bn": "গণিত",
                "chapters": [
                    ("স্বাভাবিক সংখ্যা ও ভগ্নাংশ", "Natural Numbers and Fractions"),
                    ("দশমিক ভগ্নাংশ", "Decimal Fractions"),
                    ("শতকরা", "Percentage"),
                    ("পরিমাপ", "Measurement"),
                    ("জ্যামিতি", "Geometry"),
                    ("উপাত্ত সংগ্রহ ও বিশ্লেষণ", "Data Collection and Analysis"),
                ]
            },
            "Bangladesh and Global Studies": {
                "name_bn": "বাংলাদেশ ও বিশ্বপরিচয়",
                "chapters": [
                    ("বাংলাদেশের ভূ-প্রকৃতি", "Geography of Bangladesh"),
                    ("জনসংখ্যা ও উন্নয়ন", "Population and Development"),
                    ("সম্পদ ও অর্থনীতি", "Resources and Economy"),
                    ("মহান মুক্তিযুদ্ধ", "Great Liberation War"),
                    ("বিশ্ব ভূগোল", "World Geography"),
                ]
            },
            "General Science": {
                "name_bn": "প্রাথমিক বিজ্ঞান",
                "chapters": [
                    ("জীবন ও পরিবেশ", "Life and Environment"),
                    ("পদার্থের অবস্থা", "States of Matter"),
                    ("শক্তি ও কাজ", "Energy and Work"),
                    ("পৃথিবী ও মহাবিশ্ব", "Earth and Universe"),
                    ("প্রযুক্তি ও জীবন", "Technology and Life"),
                ]
            },
        }
    },
    6: {
        "name": "Class 6",
        "name_bn": "৬ষ্ঠ শ্রেণি",
        "level": "Secondary",
        "subjects": {
            "Bangla": {
                "name_bn": "বাংলা",
                "chapters": [
                    ("সুভা", "Subha"),
                    ("বাংলা নববর্ষ", "Bengali New Year"),
                    ("লাল গরুটা", "The Red Cow"),
                    ("ভাব-সম্প্রসারণ", "Idea Expansion"),
                    ("ব্যাকরণ - ধ্বনি ও বর্ণ", "Grammar - Sound and Letters"),
                    ("সারাংশ ও সারমর্ম", "Summary"),
                ]
            },
            "English": {
                "name_bn": "ইংরেজি",
                "chapters": [
                    ("Going to a New School", "Going to a New School"),
                    ("Let's Cook", "Let's Cook"),
                    ("Sports and Games", "Sports and Games"),
                    ("Our Pastimes", "Our Pastimes"),
                    ("Tense and Sentence", "Tense and Sentence"),
                    ("Writing Skills", "Writing Skills"),
                ]
            },
            "Mathematics": {
                "name_bn": "গণিত",
                "chapters": [
                    ("স্বাভাবিক সংখ্যা ও ভগ্নাংশ", "Natural Numbers and Fractions"),
                    ("অনুপাত ও শতকরা", "Ratio and Percentage"),
                    ("বীজগাণিতিক রাশি", "Algebraic Expressions"),
                    ("সরল সমীকরণ", "Simple Equations"),
                    ("জ্যামিতি - রেখা ও কোণ", "Geometry - Lines and Angles"),
                    ("ত্রিভুজ", "Triangles"),
                    ("উপাত্ত বিশ্লেষণ", "Data Analysis"),
                ]
            },
            "General Science": {
                "name_bn": "সাধারণ বিজ্ঞান",
                "chapters": [
                    ("জীবকোষ ও টিস্যু", "Cell and Tissue"),
                    ("জীবে পরিবহন", "Transport in Living Things"),
                    ("পদার্থের গঠন", "Structure of Matter"),
                    ("শক্তির রূপান্তর", "Transformation of Energy"),
                    ("পরিবেশ ও বাস্তুতন্ত্র", "Environment and Ecosystem"),
                    ("সৌরজগৎ", "Solar System"),
                ]
            },
            "Bangladesh and Global Studies": {
                "name_bn": "বাংলাদেশ ও বিশ্বপরিচয়",
                "chapters": [
                    ("বাংলাদেশের ইতিহাস ও সংস্কৃতি", "History and Culture of Bangladesh"),
                    ("বাংলাদেশের মুক্তিযুদ্ধ", "Liberation War of Bangladesh"),
                    ("বাংলাদেশের সম্পদ", "Resources of Bangladesh"),
                    ("সামাজিক সমস্যা ও প্রতিকার", "Social Problems and Solutions"),
                    ("এশিয়া মহাদেশ", "Asian Continent"),
                ]
            },
            "ICT": {
                "name_bn": "তথ্য ও যোগাযোগ প্রযুক্তি",
                "chapters": [
                    ("তথ্য ও যোগাযোগ প্রযুক্তি পরিচিতি", "Introduction to ICT"),
                    ("কম্পিউটার পরিচিতি", "Introduction to Computers"),
                    ("ইন্টারনেট পরিচিতি", "Introduction to Internet"),
                    ("ওয়ার্ড প্রসেসিং", "Word Processing"),
                    ("নিরাপদ ইন্টারনেট ব্যবহার", "Safe Internet Usage"),
                ]
            },
        }
    },
    7: {
        "name": "Class 7",
        "name_bn": "৭ম শ্রেণি",
        "level": "Secondary",
        "subjects": {
            "Bangla": {
                "name_bn": "বাংলা",
                "chapters": [
                    ("কাবুলিওয়ালা", "Kabuliwala"),
                    ("মানুষ", "Human"),
                    ("প্রিয় বাংলাদেশ", "Dear Bangladesh"),
                    ("পত্র লিখন", "Letter Writing"),
                    ("ব্যাকরণ - শব্দ ও পদ", "Grammar - Words and Parts"),
                    ("অনুচ্ছেদ রচনা", "Paragraph Writing"),
                ]
            },
            "English": {
                "name_bn": "ইংরেজি",
                "chapters": [
                    ("The Selfish Giant", "The Selfish Giant"),
                    ("A Day in the Life of Amal", "A Day in the Life of Amal"),
                    ("Dreams", "Dreams"),
                    ("Environment", "Environment"),
                    ("Voices of Change", "Voices of Change"),
                    ("Grammar and Composition", "Grammar and Composition"),
                ]
            },
            "Mathematics": {
                "name_bn": "গণিত",
                "chapters": [
                    ("মূলদ ও অমূলদ সংখ্যা", "Rational and Irrational Numbers"),
                    ("সূচক ও লগারিদম", "Exponents and Logarithms"),
                    ("বীজগাণিতিক সূত্রাবলী", "Algebraic Formulas"),
                    ("সমীকরণ", "Equations"),
                    ("জ্যামিতি - চতুর্ভুজ", "Geometry - Quadrilaterals"),
                    ("বৃত্ত", "Circle"),
                    ("পরিসংখ্যান", "Statistics"),
                ]
            },
            "General Science": {
                "name_bn": "সাধারণ বিজ্ঞান",
                "chapters": [
                    ("জীবের বংশগতি", "Heredity of Living Things"),
                    ("মানবদেহের তন্ত্র", "Human Body Systems"),
                    ("পদার্থের রাসায়নিক পরিবর্তন", "Chemical Changes of Matter"),
                    ("তাপ ও তাপমাত্রা", "Heat and Temperature"),
                    ("আলো", "Light"),
                    ("বিদ্যুৎ ও চুম্বক", "Electricity and Magnetism"),
                ]
            },
            "Bangladesh and Global Studies": {
                "name_bn": "বাংলাদেশ ও বিশ্বপরিচয়",
                "chapters": [
                    ("প্রাচীন বাংলার ইতিহাস", "History of Ancient Bengal"),
                    ("মধ্যযুগের বাংলা", "Medieval Bengal"),
                    ("ব্রিটিশ শাসন", "British Rule"),
                    ("বাংলাদেশের সংবিধান", "Constitution of Bangladesh"),
                    ("ইউরোপ ও আমেরিকা", "Europe and America"),
                ]
            },
            "ICT": {
                "name_bn": "তথ্য ও যোগাযোগ প্রযুক্তি",
                "chapters": [
                    ("ডিজিটাল বাংলাদেশ", "Digital Bangladesh"),
                    ("স্প্রেডশিট", "Spreadsheet"),
                    ("ইন্টারনেট ও ই-মেইল", "Internet and Email"),
                    ("মাল্টিমিডিয়া", "Multimedia"),
                    ("সাইবার নিরাপত্তা", "Cyber Security"),
                ]
            },
        }
    },
    8: {
        "name": "Class 8",
        "name_bn": "৮ম শ্রেণি",
        "level": "Secondary",
        "subjects": {
            "Bangla": {
                "name_bn": "বাংলা",
                "chapters": [
                    ("অতিথির স্মৃতি", "Memory of a Guest"),
                    ("ভাবুক ছেলে", "The Thoughtful Boy"),
                    ("একুশের গান", "Song of 21st"),
                    ("বাংলা ব্যাকরণ - বাক্য", "Grammar - Sentences"),
                    ("প্রবন্ধ রচনা", "Essay Writing"),
                    ("সারাংশ লিখন", "Summary Writing"),
                ]
            },
            "English": {
                "name_bn": "ইংরেজি",
                "chapters": [
                    ("Nelson Mandela", "Nelson Mandela"),
                    ("Hazrat Umar", "Hazrat Umar"),
                    ("A Fishy Story", "A Fishy Story"),
                    ("Environment Pollution", "Environment Pollution"),
                    ("Voice and Narration", "Voice and Narration"),
                    ("Paragraph and Composition", "Paragraph and Composition"),
                ]
            },
            "Mathematics": {
                "name_bn": "গণিত",
                "chapters": [
                    ("বীজগাণিতিক রাশির গুণ ও ভাগ", "Multiplication and Division of Algebraic Expressions"),
                    ("সরল সমীকরণ", "Linear Equations"),
                    ("চতুর্ভুজ", "Quadrilaterals"),
                    ("বৃত্ত ও ক্ষেত্রফল", "Circle and Area"),
                    ("সরল মুনাফা", "Simple Interest"),
                    ("অনুপাত ও সমানুপাত", "Ratio and Proportion"),
                    ("সেট", "Set Theory"),
                ]
            },
            "General Science": {
                "name_bn": "সাধারণ বিজ্ঞান",
                "chapters": [
                    ("জীবের প্রজনন", "Reproduction in Living Things"),
                    ("খাদ্য ও পুষ্টি", "Food and Nutrition"),
                    ("অম্ল, ক্ষার ও লবণ", "Acids, Bases and Salts"),
                    ("গতি ও বল", "Motion and Force"),
                    ("শব্দ", "Sound"),
                    ("ভূগর্ভস্থ সম্পদ", "Underground Resources"),
                ]
            },
            "Bangladesh and Global Studies": {
                "name_bn": "বাংলাদেশ ও বিশ্বপরিচয়",
                "chapters": [
                    ("ভাষা আন্দোলন ও বাঙালি জাতীয়তাবাদ", "Language Movement and Bengali Nationalism"),
                    ("মুক্তিযুদ্ধ ও স্বাধীনতা", "Liberation War and Independence"),
                    ("বাংলাদেশের সরকার ব্যবস্থা", "Government System of Bangladesh"),
                    ("বাংলাদেশের অর্থনীতি", "Economy of Bangladesh"),
                    ("জাতিসংঘ ও বিশ্ব শান্তি", "UN and World Peace"),
                ]
            },
            "ICT": {
                "name_bn": "তথ্য ও যোগাযোগ প্রযুক্তি",
                "chapters": [
                    ("তথ্য প্রযুক্তির বিকাশ", "Development of IT"),
                    ("ডাটাবেজ", "Database"),
                    ("প্রেজেন্টেশন", "Presentation"),
                    ("ওয়েব ব্রাউজিং", "Web Browsing"),
                    ("ই-কমার্স ও ই-গভর্নেন্স", "E-commerce and E-governance"),
                ]
            },
        }
    },
    9: {
        "name": "Class 9",
        "name_bn": "৯ম শ্রেণি",
        "level": "Secondary",
        "subjects": {
            "Bangla": {
                "name_bn": "বাংলা",
                "chapters": [
                    ("সুভা", "Subha - Tagore"),
                    ("বঙ্গবাণী", "Bangabani"),
                    ("কপোতাক্ষ নদ", "Kapotaksha River"),
                    ("মানুষ মুহম্মদ (স:)", "Human Muhammad"),
                    ("নিমগাছ", "Neem Tree"),
                    ("আমার সন্তান", "My Child"),
                    ("বাংলা ব্যাকরণ", "Bengali Grammar"),
                    ("রচনা ও নির্মিতি", "Essay and Composition"),
                ]
            },
            "English": {
                "name_bn": "ইংরেজি",
                "chapters": [
                    ("The Ferry Boat", "The Ferry Boat"),
                    ("The Wonders of the World", "The Wonders of the World"),
                    ("Climate Change", "Climate Change"),
                    ("Dreams", "Dreams"),
                    ("Right Forms of Verbs", "Right Forms of Verbs"),
                    ("Transformation", "Transformation"),
                    ("Writing - Paragraph", "Writing - Paragraph"),
                    ("Writing - Composition", "Writing - Composition"),
                ]
            },
            "Mathematics": {
                "name_bn": "গণিত",
                "chapters": [
                    ("বাস্তব সংখ্যা", "Real Numbers"),
                    ("সেট ও ফাংশন", "Sets and Functions"),
                    ("বীজগাণিতিক রাশি", "Algebraic Expressions"),
                    ("সূচক ও লগারিদম", "Exponents and Logarithms"),
                    ("একচলক বিশিষ্ট সমীকরণ", "Equations with One Variable"),
                    ("রেখা, কোণ ও ত্রিভুজ", "Lines, Angles and Triangles"),
                    ("ত্রিকোণমিতিক অনুপাত", "Trigonometric Ratios"),
                    ("পরিসংখ্যান", "Statistics"),
                ]
            },
            "Physics": {
                "name_bn": "পদার্থবিজ্ঞান",
                "chapters": [
                    ("ভৌত রাশি ও পরিমাপ", "Physical Quantities and Measurement"),
                    ("গতি", "Motion"),
                    ("বল", "Force"),
                    ("কাজ, ক্ষমতা ও শক্তি", "Work, Power and Energy"),
                    ("পদার্থের অবস্থা ও চাপ", "States of Matter and Pressure"),
                    ("তাপ ও তাপমাত্রা", "Heat and Temperature"),
                    ("তরঙ্গ ও শব্দ", "Waves and Sound"),
                ]
            },
            "Chemistry": {
                "name_bn": "রসায়ন",
                "chapters": [
                    ("রসায়নের ধারণা", "Concept of Chemistry"),
                    ("পদার্থের অবস্থা", "States of Matter"),
                    ("পদার্থের গঠন", "Structure of Matter"),
                    ("পর্যায় সারণি", "Periodic Table"),
                    ("রাসায়নিক বন্ধন", "Chemical Bonding"),
                    ("রাসায়নিক বিক্রিয়া", "Chemical Reactions"),
                    ("এসিড-ক্ষার সমতা", "Acid-Base Balance"),
                ]
            },
            "Biology": {
                "name_bn": "জীববিজ্ঞান",
                "chapters": [
                    ("জীবন পাঠ", "Life Science"),
                    ("জীবকোষ ও টিস্যু", "Cell and Tissue"),
                    ("কোষ বিভাজন", "Cell Division"),
                    ("জীবনীশক্তি", "Bioenergetics"),
                    ("খাদ্য, পুষ্টি ও পরিপাক", "Food, Nutrition and Digestion"),
                    ("পরিবহন", "Transport"),
                    ("গ্যাসীয় বিনিময়", "Gaseous Exchange"),
                ]
            },
            "Bangladesh and Global Studies": {
                "name_bn": "বাংলাদেশ ও বিশ্বপরিচয়",
                "chapters": [
                    ("পূর্ব বাংলার আন্দোলন ও জাতীয়তাবাদ", "Movement in East Bengal"),
                    ("১৯৭১ এর মুক্তিযুদ্ধ", "Liberation War of 1971"),
                    ("সংবিধান ও নাগরিকতা", "Constitution and Citizenship"),
                    ("বাংলাদেশের অর্থনীতি ও সম্পদ", "Economy and Resources"),
                    ("আন্তর্জাতিক সম্পর্ক", "International Relations"),
                ]
            },
            "ICT": {
                "name_bn": "তথ্য ও যোগাযোগ প্রযুক্তি",
                "chapters": [
                    ("বিশ্বগ্রাম ও ডিজিটাল বাংলাদেশ", "Global Village and Digital Bangladesh"),
                    ("কম্পিউটার হার্ডওয়্যার", "Computer Hardware"),
                    ("সফটওয়্যার", "Software"),
                    ("প্রোগ্রামিং ধারণা", "Programming Concepts"),
                    ("ওয়েব ডিজাইন পরিচিতি", "Web Design Introduction"),
                ]
            },
        }
    },
    10: {
        "name": "Class 10",
        "name_bn": "১০ম শ্রেণি",
        "level": "Secondary",
        "subjects": {
            "Bangla": {
                "name_bn": "বাংলা",
                "chapters": [
                    ("বই পড়া", "Book Reading"),
                    ("প্রবাস বন্ধু", "Friend Abroad"),
                    ("সাম্যবাদী", "Equality"),
                    ("ঐকতান", "Harmony"),
                    ("বাংলা ব্যাকরণ ও রচনা", "Grammar and Essay"),
                    ("সারাংশ ও সারমর্ম", "Summary"),
                    ("পত্র লিখন", "Letter Writing"),
                    ("প্রতিবেদন", "Report Writing"),
                ]
            },
            "English": {
                "name_bn": "ইংরেজি",
                "chapters": [
                    ("At a Railway Station", "At a Railway Station"),
                    ("The Cabuliwallah", "The Cabuliwallah"),
                    ("Sheikh Saadi", "Sheikh Saadi"),
                    ("Trees", "Trees"),
                    ("Completing Sentences", "Completing Sentences"),
                    ("Passage Narration", "Passage Narration"),
                    ("Composition", "Composition"),
                    ("Dialogue and Email", "Dialogue and Email"),
                ]
            },
            "Mathematics": {
                "name_bn": "গণিত",
                "chapters": [
                    ("সেট ও ফাংশন", "Sets and Functions"),
                    ("বীজগাণিতিক সূত্রাবলি", "Algebraic Formulas"),
                    ("সরল সহসমীকরণ", "Simultaneous Linear Equations"),
                    ("সূচক ও লগারিদম", "Exponents and Logarithms"),
                    ("অনুপাত, সমানুপাত ও প্রয়োগ", "Ratio and Proportion"),
                    ("জ্যামিতি - সর্বসমতা ও সদৃশতা", "Congruence and Similarity"),
                    ("পিথাগোরাসের উপপাদ্য", "Pythagorean Theorem"),
                    ("বৃত্ত", "Circle"),
                    ("ত্রিকোণমিতি", "Trigonometry"),
                    ("পরিমিতি", "Mensuration"),
                    ("পরিসংখ্যান ও সম্ভাব্যতা", "Statistics and Probability"),
                ]
            },
            "Physics": {
                "name_bn": "পদার্থবিজ্ঞান",
                "chapters": [
                    ("ভৌত রাশি ও পরিমাপ", "Physical Quantities"),
                    ("গতি", "Motion"),
                    ("বল", "Force"),
                    ("কাজ, ক্ষমতা ও শক্তি", "Work, Power, Energy"),
                    ("তরঙ্গ ও শব্দ", "Waves and Sound"),
                    ("আলোর প্রতিফলন", "Reflection of Light"),
                    ("আলোর প্রতিসরণ", "Refraction of Light"),
                    ("স্থির তড়িৎ", "Static Electricity"),
                    ("চল তড়িৎ", "Current Electricity"),
                    ("জীবন বাঁচাতে পদার্থবিজ্ঞান", "Physics for Life"),
                ]
            },
            "Chemistry": {
                "name_bn": "রসায়ন",
                "chapters": [
                    ("রাসায়নিক পরিবর্তন", "Chemical Changes"),
                    ("পদার্থের গঠন", "Structure of Matter"),
                    ("পর্যায় সারণি", "Periodic Table"),
                    ("রাসায়নিক বন্ধন", "Chemical Bonding"),
                    ("রাসায়নিক বিক্রিয়া", "Chemical Reactions"),
                    ("অম্ল, ক্ষারক ও লবণ", "Acids, Bases and Salts"),
                    ("খনিজ সম্পদ", "Mineral Resources"),
                    ("আমাদের জীবনে রসায়ন", "Chemistry in Our Life"),
                ]
            },
            "Biology": {
                "name_bn": "জীববিজ্ঞান",
                "chapters": [
                    ("জীবের প্রজনন", "Reproduction in Living Things"),
                    ("বংশগতি ও বিবর্তন", "Heredity and Evolution"),
                    ("জীবের পরিবেশ", "Environment of Living Things"),
                    ("জীবপ্রযুক্তি", "Biotechnology"),
                    ("সমন্বয় ও নিয়ন্ত্রণ", "Coordination and Control"),
                    ("রেচন", "Excretion"),
                    ("চলন ও অঙ্গ সঞ্চালন", "Movement and Locomotion"),
                    ("জীববৈচিত্র্য", "Biodiversity"),
                ]
            },
            "Bangladesh and Global Studies": {
                "name_bn": "বাংলাদেশ ও বিশ্বপরিচয়",
                "chapters": [
                    ("ঔপনিবেশিক যুগ ও বাংলার স্বাধীনতা", "Colonial Era and Bengal's Independence"),
                    ("বাংলাদেশের অভ্যুদয়", "Emergence of Bangladesh"),
                    ("বাংলাদেশের জনসংখ্যা ও উন্নয়ন", "Population and Development"),
                    ("বাংলাদেশের পররাষ্ট্রনীতি", "Foreign Policy of Bangladesh"),
                    ("বিশ্বায়ন ও আঞ্চলিক সহযোগিতা", "Globalization and Regional Cooperation"),
                ]
            },
            "ICT": {
                "name_bn": "তথ্য ও যোগাযোগ প্রযুক্তি",
                "chapters": [
                    ("তথ্য প্রযুক্তি ও সমাজ", "IT and Society"),
                    ("কম্পিউটার ও কম্পিউটার ব্যবহারকারী", "Computer and Users"),
                    ("সংখ্যা পদ্ধতি", "Number Systems"),
                    ("প্রোগ্রামিং ভাষা", "Programming Languages"),
                    ("HTML ও ওয়েব ডিজাইন", "HTML and Web Design"),
                    ("ডাটাবেজ ম্যানেজমেন্ট", "Database Management"),
                ]
            },
        }
    },
}


def seed_nctb():
    """Seed database with NCTB curriculum"""
    app = create_app()
    with app.app_context():
        created_classes = 0
        created_subjects = 0
        created_chapters = 0

        for class_num, class_data in NCTB_DATA.items():
            # Check if class already exists
            existing_class = Class.query.filter_by(name=class_data["name"]).first()
            if existing_class:
                print(f"⚠ Class {class_data['name']} already exists, skipping...")
                cls = existing_class
            else:
                cls = Class(
                    name=class_data["name"],
                    name_bn=class_data["name_bn"],
                    level=class_data["level"],
                    order=class_num
                )
                db.session.add(cls)
                db.session.flush()
                created_classes += 1
                print(f"✓ Created class: {class_data['name']} ({class_data['name_bn']})")

            # Add subjects
            for subj_name, subj_data in class_data["subjects"].items():
                existing_subject = Subject.query.filter_by(
                    name=subj_name, class_id=cls.id
                ).first()
                
                if existing_subject:
                    subj = existing_subject
                else:
                    subj = Subject(
                        name=subj_name,
                        name_bn=subj_data["name_bn"],
                        class_id=cls.id,
                        order=list(class_data["subjects"].keys()).index(subj_name) + 1
                    )
                    db.session.add(subj)
                    db.session.flush()
                    created_subjects += 1
                    print(f"  ✓ Subject: {subj_name} ({subj_data['name_bn']})")

                # Add chapters
                for idx, (chap_bn, chap_en) in enumerate(subj_data["chapters"], 1):
                    existing_chapter = Chapter.query.filter_by(
                        name_bn=chap_bn, subject_id=subj.id
                    ).first()
                    
                    if not existing_chapter:
                        chap = Chapter(
                            name=chap_en,
                            name_bn=chap_bn,
                            chapter_number=idx,
                            subject_id=subj.id,
                            order=idx
                        )
                        db.session.add(chap)
                        created_chapters += 1

        db.session.commit()
        print("\n" + "=" * 50)
        print("NCTB Curriculum Seeding Complete!")
        print(f"  Classes created:  {created_classes}")
        print(f"  Subjects created: {created_subjects}")
        print(f"  Chapters created: {created_chapters}")
        print("=" * 50)


if __name__ == "__main__":
    seed_nctb()
