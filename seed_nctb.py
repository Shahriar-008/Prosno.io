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
                    ("পার্টনার", "Partnership"),
                    ("মুনাফা", "Profit"),
                    ("পরিমাপ", "Measurement"),
                    ("বীজগণিতীয় সূত্রাবলি ও প্রয়োগ", "Algebraic Formulas and Applications"),
                    ("বীজগণিতীয় ভগ্নাংশ", "Algebraic Fractions"),
                    ("সমুহ সংখ্যাময়ীকরণ", "Factorization"),
                    ("সেট", "Set"),
                    ("চতুর্ভুজ", "Quadrilateral"),
                    ("পিপাটারোগের উপাদান", "Pythagorean Components"),
                    ("বৃত্ত", "Circle"),
                    ("লেখ ও উপাদি", "Graph and Data"),
                ]
            },
            "General Science": {
                "name_bn": "সাধারণ বিজ্ঞান",
                "chapters": [
                    ("প্রাণিজগতের শ্রেণীবিন্যাস", "Classification of Animals"),
                    ("জীবের বৃদ্ধি ও বংশগতি", "Growth and Heredity of Organisms"),
                    ("ব্যান, অভিভরণ ও প্রবেশন", "Cell, Diffusion and Osmosis"),
                    ("উদ্ভিদের নমন বৃদ্ধি", "Tropism in Plants"),
                    ("সমন্বয় ও নিয়ন্ত্রণ", "Coordination and Control"),
                    ("পরিমণুর গঠন", "Atomic Structure"),
                    ("পূর্বরী ও মহাশক্তি", "Force and Momentum"),
                    ("রাসায়নিক বিক্রিয়া", "Chemical Reactions"),
                    ("বংশগতি ও চরিত্রগুরু", "Heredity and Variation"),
                    ("অম্ল, ক্ষারক ও লবণ", "Acids, Bases and Salts"),
                    ("আলো", "Light"),
                    ("মহাকাশ ও উপগ্রহ", "Space and Satellites"),
                    ("খাদ্য ও পুষ্টি", "Food and Nutrition"),
                    ("পরিবেশ এবং বাস্তুতন্ত্র", "Environment and Ecosystem"),
                ]
            },
            "Bangladesh and Global Studies": {
                "name_bn": "বাংলাদেশ ও বিশ্বপরিচয়",
                "chapters": [
                    ("উপনিবেশিক যুগ ও বাংলার দ্বৈতশাসন ব্যবস্থা", "Colonial Era and Dual Governance in Bengal"),
                    ("উপনিবেশিক শুভের প্রতিক্রিয়ার প্রতিক্রিয়া", "Reactions to Colonial Exploitation"),
                    ("বাংলাদেশের মুক্তিযুদ্ধ ও পরবর্তী সমস্যা", "Liberation War and Post-War Problems"),
                    ("বাংলাদেশের অর্থনীতি", "Economy of Bangladesh"),
                    ("বাংলাদেশ : নারী ও সবার বন্ধু", "Bangladesh: Women and Friends of All"),
                    ("বাংলাদেশের সাংস্কৃতিক পরিচয়", "Cultural Identity of Bangladesh"),
                    ("সামাজিকীকরণ", "Socialization"),
                    ("বাংলাদেশের মানবীয় মূল্যবোধ", "Human Values of Bangladesh"),
                    ("বাংলাদেশের সামাজিক সমস্যা", "Social Problems of Bangladesh"),
                    ("বাংলাদেশের জনসংখ্যা ও উন্নয়ন", "Population and Development of Bangladesh"),
                    ("বাংলাদেশে জলবায়ু ও পূর্বীণ মোকাবিলা", "Climate Change and Disaster Management in Bangladesh"),
                    ("বাংলাদেশের প্রাকৃতিক সম্পদ", "Natural Resources of Bangladesh"),
                    ("বাংলাদেশ এবং বিভিন্ন আঞ্চলিক ও আন্তর্জাতিক সংস্থা", "Bangladesh and Various Regional and International Organizations"),
                ]
            },
            "ICT": {
                "name_bn": "তথ্য ও যোগাযোগ প্রযুক্তি",
                "chapters": [
                    ("তথ্য ও যোগাযোগ প্রযুক্তির পূর্বরূপ", "Overview of ICT"),
                    ("কম্পিউটার নেটওয়ার্ক", "Computer Network"),
                    ("তথ্য ও যোগাযোগ প্রযুক্তির নিরাপদ ও নৈতিক ব্যবহার", "Safe and Ethical Use of ICT"),
                    ("সংখ্যাপদ্ধতির ব্যবহার", "Use of Number Systems"),
                    ("শিক্ষা ও দৈনন্দিন জীবনে ইন্টারনেটের ব্যবহার", "Use of Internet in Education and Daily Life"),
                ]
            },
            "Physical Education and Health": {
                "name_bn": "শারীরিক শিক্ষা ও স্বাস্থ্য",
                "chapters": [
                    ("শরীরচর্চা ও সুস্থীকরণ", "Physical Exercise and Wellness"),
                    ("স্কাউটিং, গার্ল গাইডিং ও বাংলাদেশ রেড ক্রিসেন্ট সোসাইটি", "Scouting, Girl Guiding and Bangladesh Red Crescent Society"),
                    ("আমাদের জীবনে প্রজনন স্বাস্থ্য", "Reproductive Health in Our Lives"),
                    ("জীবনের জন্য খেলাধুলা", "Sports for Life"),
                ]
            },
            "Work and Life Oriented Education": {
                "name_bn": "কর্ম ও জীবনমুখী শিক্ষা",
                "chapters": [
                    ("মেধা, কার্যক্রম ও আত্ম-অনুসন্ধান", "Creativity, Activities and Self-Discovery"),
                    ("আমাদের কাজ: যেগুলো অন্যরা করে", "Our Work: Jobs Done by Others"),
                    ("আমাদের শিক্ষা ও কর্ম", "Our Education and Work"),
                ]
            },
            "Agriculture Studies": {
                "name_bn": "কৃষি শিক্ষা",
                "chapters": [
                    ("বাংলাদেশের কৃষি ও আন্তর্জাতিক প্রেক্ষাপট", "Bangladesh Agriculture and International Perspective"),
                    ("কৃষিপ্রযুক্তি", "Agricultural Technology"),
                    ("কৃষি উপকরণ", "Agricultural Tools and Equipment"),
                    ("কৃষি ও জলবায়ু", "Agriculture and Climate"),
                    ("কৃষি উৎপাদন", "Agricultural Production"),
                    ("বনায়ন", "Afforestation"),
                ]
            },
        }
    },
    9: {
        "name": "SSC",
        "name_bn": "এসএসসি",
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
            "Higher Mathematics": {
                "name_bn": "উচ্চতর গণিত",
                "chapters": [
                    ("সেট ও ফাংশন", "Sets and Functions"),
                    ("বীজগাণিতিক রাশি", "Algebraic Expressions"),
                    ("জ্যামিতি", "Geometry"),
                    ("জ্যামিতিক অঙ্কন", "Geometric Drawing"),
                    ("সমীকরণ", "Equations"),
                    ("অসমতা", "Inequality"),
                    ("অসীম ধারা", "Infinite Series"),
                    ("ত্রিকোণমিতি", "Trigonometry"),
                    ("সূচকীয় ও লগারিদমীয় ফাংশন", "Exponential and Logarithmic Functions"),
                    ("দ্বিপদী বিস্তৃতি", "Binomial Expansion"),
                    ("স্থানাঙ্ক জ্যামিতি", "Coordinate Geometry"),
                    ("সমষ্টিগত তত্ত্ব", "Combinatorics"),
                    ("ঘন জ্যামিতি", "Solid Geometry"),
                    ("সম্ভাবনা", "Probability"),
                ]
            },
            "Physics": {
                "name_bn": "পদার্থবিজ্ঞান",
                "chapters": [
                    ("ভৌত রাশি এবং তাদের পরিমাপ", "Physical Quantities and Measurement"),
                    ("গতি", "Motion"),
                    ("বল", "Force"),
                    ("কাজ, ক্ষমতা ও শক্তি", "Work, Power and Energy"),
                    ("পদার্থের অবস্থা ও চাপ", "States of Matter and Pressure"),
                    ("বস্তুর উপর তাপের প্রভাব", "Effect of Heat on Objects"),
                    ("তরঙ্গ ও শব্দ", "Waves and Sound"),
                    ("আলোর প্রতিফলন", "Reflection of Light"),
                    ("আলোর প্রতিসরণ", "Refraction of Light"),
                    ("স্থির বিদ্যুৎ", "Static Electricity"),
                    ("চল বিদ্যুৎ", "Current Electricity"),
                    ("বিদ্যুতের চৌম্বক ক্রিয়া", "Magnetic Effects of Electricity"),
                    ("তেজস্ক্রিয়তা ও পরমাণু শক্তি", "Radioactivity and Nuclear Energy"),
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
                    ("মোলের ধারণা ও রাসায়নিক গণনা", "Mole Concept and Chemical Calculations"),
                    ("রাসায়নিক বিক্রিয়া", "Chemical Reactions"),
                    ("রসায়ন ও শক্তি", "Chemistry and Energy"),
                    ("এসিড-ক্ষারক সমতা", "Acid-Base Balance"),
                    ("খনিজ সম্পদ: ধাতু-অধাতু", "Mineral Resources: Metals-Nonmetals"),
                    ("খনিজ সম্পদ: জীবাশ্ম", "Mineral Resources: Fossils"),
                    ("আমাদের জীবনে রসায়ন", "Chemistry in Our Life"),
                ]
            },
            "Biology": {
                "name_bn": "জীববিজ্ঞান",
                "chapters": [
                    ("জীবনপাঠ", "Life Science"),
                    ("জীবকোষ ও টিস্যু", "Cell and Tissue"),
                    ("কোষ বিভাজন", "Cell Division"),
                    ("জীবনীশক্তি", "Bioenergetics"),
                    ("খাদ্য, পুষ্টি এবং পরিপাক", "Food, Nutrition and Digestion"),
                    ("জীব পরিবহন", "Transport"),
                    ("গ্যাসীয় বিনিময়", "Gaseous Exchange"),
                    ("রেচন প্রক্রিয়া", "Excretion Process"),
                    ("দৃঢ়তা প্রদান ও চলন", "Rigidity and Movement"),
                    ("সমন্বয়", "Coordination"),
                    ("জীবের প্রজনন", "Reproduction in Living Things"),
                    ("জীবের বংশগতি ও জিন প্রযুক্তি", "Heredity and Genetic Engineering"),
                    ("জীবের পরিবেশ", "Environment of Living Things"),
                    ("জীবপ্রযুক্তি", "Biotechnology"),
                ]
            },
            "Bangladesh and Global Studies": {
                "name_bn": "বাংলাদেশ ও বিশ্বপরিচয়",
                "chapters": [
                    ("পূর্ব বাংলার আন্দোলন ও জাতীয়তাবাদের উত্থান (১৯৪৭-১৯৭০)", "Movement in East Bengal and Rise of Nationalism (1947-1970)"),
                    ("বাংলাদেশের স্বাধীনতা", "Independence of Bangladesh"),
                    ("সৌরলক্ষ্য ও তুঙ্গভদ্র", "Solar System and Tungabhadra"),
                    ("বাংলাদেশের ভূ-প্রকৃতি ও জলবায়ু", "Geography and Climate of Bangladesh"),
                    ("বাংলাদেশের নদ-নদী ও প্রাকৃতিক সম্পদ", "Rivers and Natural Resources of Bangladesh"),
                    ("রাষ্ট্র, নাগরিকতা ও আইন", "State, Citizenship and Law"),
                    ("বাংলাদেশ সরকারের বিভিন্ন অঙ্গ ও এদসমূহ ব্যবস্থা", "Different Organs of Bangladesh Government and Their System"),
                    ("বাংলাদেশের গণতন্ত্র ও নির্বাচন ব্যবস্থা", "Democracy and Electoral System of Bangladesh"),
                    ("জাতিসংঘ ও বাংলাদেশ", "United Nations and Bangladesh"),
                    ("জাতীয় সম্পদ ও অর্থনৈতিক ব্যবস্থা", "National Resources and Economic System"),
                    ("অর্থনৈতিক উন্নয়নকমূহ ও বাংলাদেশের অর্থনীতির প্রকৃতি", "Economic Development and Nature of Bangladesh Economy"),
                    ("বাংলাদেশ সরকারের ধর্ম ও ব্যাংক ব্যবস্থা", "Religion and Banking System of Bangladesh Government"),
                    ("বাংলাদেশের পরিবার কাঠামো ও সামাজিকীকরণ", "Family Structure and Socialization in Bangladesh"),
                    ("বাংলাদেশের সামাজিক পরিবর্তন", "Social Change in Bangladesh"),
                    ("বাংলাদেশের সামাজিক সমস্যা ও প্রতিকার", "Social Problems and Solutions in Bangladesh"),
                ]
            },
            "Geography and Environment": {
                "name_bn": "ভূগোল ও পরিবেশ",
                "chapters": [
                    ("ভূগোল ও পরিবেশ", "Geography and Environment"),
                    ("মহাবিশ্ব ও আমাদের পৃথিবী", "Universe and Our Earth"),
                    ("মানচিত্র পঠন ও ব্যবহার", "Map Reading and Use"),
                    ("পৃথিবীর অক্ষরেখাীয় ও বাহিরের পঠন", "Latitudinal and External Reading of Earth"),
                    ("বায়ুমন্ডল", "Atmosphere"),
                    ("বারিমন্ডল", "Hydrosphere"),
                    ("জনসংখ্যা", "Population"),
                    ("মানবকর্মী", "Human Resources"),
                    ("সম্পদ ও অর্থনৈতিক কার্যাবলি", "Resources and Economic Activities"),
                    ("বাংলাদেশের জৈসম্পদীয় বিস্তার", "Biodiversity Distribution of Bangladesh"),
                    ("বাংলাদেশের সম্পদ ও শিল্প", "Resources and Industries of Bangladesh"),
                    ("বাংলাদেশের জনসংখ্যা বৃদ্ধি ও বিশেষণ", "Population Growth and Analysis of Bangladesh"),
                    ("বাংলাদেশের উন্নয়ন সম্ভাবনা ও পরিকল্পিত ভূমিকায়", "Development Potential and Planned Role of Bangladesh"),
                    ("বাংলাদেশের প্রাকৃতিক সম্পদের", "Natural Resources of Bangladesh"),
                    ("সংকট উন্নয়ন-আগতি (এফডিআই)", "Crisis Development-FDI"),
                ]
            },
            "Economics": {
                "name_bn": "অর্থনীতি",
                "chapters": [
                    ("অর্থনীতি পরিচয়", "Introduction to Economics"),
                    ("অর্থনীতির তত্ত্বপূর্ণ ধারাসমূহ", "Theoretical Streams of Economics"),
                    ("উৎপাদন, চাহিদা, জোগান ও ভারসাম্য", "Production, Demand, Supply and Equilibrium"),
                    ("উৎপাদন ও সংগঠন", "Production and Organization"),
                    ("বাজার", "Market"),
                    ("জাতীয় আয় ও এর পরিমাপ", "National Income and Its Measurement"),
                    ("অর্থ ও ব্যাংকব্যবস্থা", "Money and Banking System"),
                    ("বাংলাদেশের অর্থনীতি", "Economy of Bangladesh"),
                    ("বাংলাদেশের তুলনপূর্ণ অর্থনৈতিক প্রসঙ্গ", "Comparative Economic Issues of Bangladesh"),
                    ("বাংলাদেশ সরকারের অর্থব্যবস্থা", "Financial System of Bangladesh Government"),
                ]
            },
            "Agriculture Studies": {
                "name_bn": "কৃষি শিক্ষা",
                "chapters": [
                    ("কৃষি প্রযুক্তি", "Agricultural Technology"),
                    ("কৃষি উপকরণ", "Agricultural Inputs"),
                    ("কৃষি ও জলবায়ু", "Agriculture and Climate"),
                    ("কৃষিজ উৎপাদন", "Agricultural Production"),
                    ("বনায়ন", "Forestation"),
                    ("কৃষি সমবায়", "Agricultural Cooperative"),
                    ("পারিবারিক খামার", "Family Farm"),
                ]
            },
            "Home Science": {
                "name_bn": "গার্হস্থ্য বিজ্ঞান",
                "chapters": [
                    ("ব্যক্তিগত, পারিবারিক ও সামাজিক মূল্যবোধ", "Personal, Family and Social Values"),
                    ("পুষ্টি প্রয়োজনীয়তা", "Nutritional Requirements"),
                    ("পুষ্টি সমস্যা", "Nutritional Problems"),
                    ("সুস্বাস্থ্য", "Good Health"),
                    ("মুদ্রা সংরক্ষণ সংকো", "Currency Conservation Crisis"),
                    ("বিশেষ শিশুর পরিচর্যা ও সমস্যাসমূহ", "Care and Problems of Special Children"),
                    ("শিশু যত্ন ও প্রশিক্ষণ", "Child Care and Training"),
                    ("শিশুর বিশেষ ও সামাজিক পরিবেশ", "Special and Social Environment of Children"),
                    ("শৈশবকালীন স্বাস্থ্যবিধি করণন ও খেলা পরিচর্যা", "Childhood Health Care and Play Care"),
                    ("প্রশিক্ষণ সিদ্ধান্ত", "Training Decisions"),
                    ("বয়ন কলা ও বালা মেরামত", "Weaving Art and Bala Repair"),
                    ("হাতের কাজ ও ডিজাইন", "Handicraft and Design"),
                    ("বাংলাদেশে নিয়মিত করণ ও সম্ভাব্য সমস্যার তুলনা", "Regular Operation and Comparison of Potential Problems in Bangladesh"),
                    ("গৃহ সজ্জা ও সাজসজ্জা", "Home Decoration and Furnishing"),
                    ("হোটেল বিশেষ ব্যবসায়িক কম্পনি ও বাল্য মেরামত", "Hotel Special Business Companies and Child Repair"),
                    ("সিল্ক ও খাবা মেরামত", "Silk and Khaba Repair"),
                    ("পার্ক মন্ডল", "Park Mandal"),
                    ("ছিমে চালক ও কাঠামো", "Chime Driver and Structure"),
                    ("কেক মান্ড ও কেকনমী", "Cake Making and Economy"),
                    ("সবজ্জী চাক", "Vegetable Cultivation"),
                    ("মাইক্রোওয়েভ কাঠামো", "Microwave Structure"),
                    ("মেঘবল চহ্য ও পরিমান্ডি", "Cloud Power and Mandapam"),
                ]
            },
            "Civics and Citizenship": {
                "name_bn": "পৌরনীতি ও নাগরিকতা",
                "chapters": [
                    ("পৌরনীতি ও নাগরিকতা", "Civics and Citizenship"),
                    ("নাগরিক ও নাগরিকতা", "Citizens and Citizenship"),
                    ("আইন, স্বাধীনতা ও সাম্য", "Law, Freedom and Equality"),
                    ("রাষ্ট্র ও সরকার ব্যবস্থা", "State and Government System"),
                    ("সংবিধান", "Constitution"),
                    ("বাংলাদেশের সরকার ব্যবস্থা", "Government System of Bangladesh"),
                    ("গণতন্ত্র রাজনৈতিক দল ও নির্বাচন ব্যবস্থা", "Democracy, Political Parties and Electoral System"),
                    ("বাংলাদেশের স্থানীয় সরকার ব্যবস্থা", "Local Government System of Bangladesh"),
                    ("নাগরিক সমস্যা ও আমাদের করণীয়", "Civic Problems and Our Responsibilities"),
                    ("বাংলাদেশ ও আন্তর্জাতিক সংগঠন", "Bangladesh and International Organizations"),
                ]
            },
            "Accounting": {
                "name_bn": "হিসাববিজ্ঞান",
                "chapters": [
                    ("হিসাববিজ্ঞান পরিচিতি", "Introduction to Accounting"),
                    ("লেনদেন", "Transactions"),
                    ("দু তরফা দাখিলা পদ্ধতি", "Double Entry System"),
                    ("মূলধন ও মুনাফা জাতীয় লেনদেন", "Capital and Revenue Transactions"),
                    ("হিসাব", "Accounts"),
                    ("জাবেদা", "Journal"),
                    ("খতিয়ান", "Ledger"),
                    ("নগদান বই", "Cash Book"),
                    ("রেওয়ামিল", "Trial Balance"),
                    ("আর্থিক বিবরণী", "Financial Statements"),
                    ("পণ্যের ক্রয়মূল্য, উৎপাদন ব্যয় ও বিক্রয়মূল্য", "Cost Price, Production Cost and Selling Price"),
                    ("পারিবারিক ও আত্মকর্মসংস্থানমূলক উদ্যোগের হিসাব", "Family and Self-Employment Venture Accounting"),
                ]
            },
            "Finance and Banking": {
                "name_bn": "ফিন্যান্স ও ব্যাংকিং",
                "chapters": [
                    ("অর্থায়ন ও ব্যবসায় অর্থায়ন", "Finance and Business Finance"),
                    ("অর্থায়নের উৎস", "Sources of Finance"),
                    ("শেয়ার, বন্ড ও ডিবেঞ্চার", "Shares, Bonds and Debentures"),
                    ("অংশের সমস্যুল্য", "Problem of Partnership"),
                    ("মূল্ক ও অবমূল্যায়ন", "Valuation and Depreciation"),
                    ("মূলধন আয়-ব্যয় প্রাক্কলন", "Capital Budget Estimation"),
                    ("মূলধন ব্যয়", "Capital Expenditure"),
                    ("মুদ্রা, ব্যাংক ও ব্যাংকিং", "Money, Bank and Banking"),
                    ("ব্যাংকিং ব্যবসায় ও তার ধরন", "Banking Business and Its Types"),
                    ("বানিজ্যিক ব্যাংক", "Commercial Bank"),
                    ("ব্যাংকের আমানত", "Bank Deposits"),
                    ("ব্যাংক ও ঋণ", "Bank and Loan"),
                    ("কেন্দ্রীয় ব্যাংক", "Central Bank"),
                ]
            },
            "Business Entrepreneurship": {
                "name_bn": "ব্যবসায় উদ্যোগ",
                "chapters": [
                    ("ব্যবসায় পরিচিতি", "Introduction to Business"),
                    ("ব্যবসায় উদ্যোগ ও উদ্যোক্তা", "Business Venture and Entrepreneur"),
                    ("আত্মকর্মসংস্থান", "Self-Employment"),
                    ("দামিকীরণ তিষ্টিতে ব্যবসায়", "Business in Pricing Perspective"),
                    ("ব্যবসায়ের আইনগত দিক", "Legal Aspects of Business"),
                    ("ব্যবসায় পরিকল্পনা", "Business Planning"),
                    ("বাংলাদেশের শিল্প", "Industries of Bangladesh"),
                    ("ব্যবসায় প্রতিষ্ঠানের ব্যবস্থাপনা", "Business Organization Management"),
                    ("বিপণন", "Marketing"),
                    ("ব্যবসায় উদ্যোগ উন্নয়নে সহায়ক সেবা", "Support Services for Business Development"),
                    ("ব্যবসায় ঐতিহাত্র ও সামাজিক দায়িত্ব", "Business Ethics and Social Responsibility"),
                    ("সক্ষম উদ্যোক্তাদের জীবনী থেকে শিক্ষণীয়", "Lessons from Successful Entrepreneurs"),
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
        "name": "HSC",
        "name_bn": "এইচএসসি",
        "level": "Higher Secondary",
        "subjects": {
            "Bangla 1st Paper": {
                "name_bn": "বাংলা ১ম পত্র",
                "chapters": [
                    ("অপরিচিতা", "Oporichita - Tagore"),
                    ("বিলাসী", "Bilashi - Sarat Chandra"),
                    ("মাসি-পিসি", "Mashi-Pishi - Manik"),
                    ("জীবন ও বৃক্ষ", "Life and Tree"),
                    ("মহাজাগতিক কিউরেটর", "Cosmic Curator"),
                    ("আমার পথ", "My Path - Nazrul"),
                    ("বিড়াল", "The Cat - Bankim"),
                    ("চাষার দুক্ষু", "Farmer's Sorrow"),
                    ("সোনার তরী", "Golden Boat - Tagore"),
                    ("আঠারো বছর বয়স", "Eighteen Years Old - Sukanta"),
                ]
            },
            "Bangla 2nd Paper": {
                "name_bn": "বাংলা ২য় পত্র",
                "chapters": [
                    ("বাংলা ভাষার ইতিহাস", "History of Bengali Language"),
                    ("শব্দ ও পদ প্রকরণ", "Word and Parts of Speech"),
                    ("বাক্য প্রকরণ", "Sentence Structure"),
                    ("প্রবন্ধ রচনা", "Essay Writing"),
                    ("সারাংশ ও সারমর্ম", "Summary and Précis"),
                    ("ভাব-সম্প্রসারণ", "Idea Expansion"),
                    ("পত্র লিখন", "Letter Writing"),
                    ("প্রতিবেদন প্রণয়ন", "Report Writing"),
                ]
            },
            "English 1st Paper": {
                "name_bn": "ইংরেজি ১ম পত্র",
                "chapters": [
                    ("The Luncheon", "The Luncheon - Maugham"),
                    ("A Mother in Mannville", "A Mother in Mannville"),
                    ("Two Women", "Two Women"),
                    ("The Ant and the Grasshopper", "The Ant and the Grasshopper"),
                    ("I Have a Dream", "I Have a Dream - MLK"),
                    ("The Lake Isle of Innisfree", "The Lake Isle of Innisfree"),
                    ("God's Minute", "God's Minute"),
                    ("The Charge of the Light Brigade", "The Charge of the Light Brigade"),
                ]
            },
            "English 2nd Paper": {
                "name_bn": "ইংরেজি ২য় পত্র",
                "chapters": [
                    ("Tense", "Tense"),
                    ("Right Forms of Verbs", "Right Forms of Verbs"),
                    ("Narration", "Narration"),
                    ("Transformation", "Transformation"),
                    ("Sentence Connectors", "Sentence Connectors"),
                    ("Paragraph Writing", "Paragraph Writing"),
                    ("Report Writing", "Report Writing"),
                    ("Application and Letter", "Application and Letter"),
                    ("Essay Writing", "Essay Writing"),
                ]
            },
            "Physics 1st Paper": {
                "name_bn": "পদার্থবিজ্ঞান ১ম পত্র",
                "chapters": [
                    ("ভৌত জগৎ ও পরিমাপ", "Physical World and Measurement"),
                    ("ভেক্টর", "Vectors"),
                    ("গতিবিদ্যা", "Kinematics"),
                    ("নিউটনীয় বলবিদ্যা", "Newtonian Mechanics"),
                    ("কাজ, শক্তি ও ক্ষমতা", "Work, Energy and Power"),
                    ("মহাকর্ষ ও অভিকর্ষ", "Gravitation"),
                    ("পদার্থের গাঠনিক ধর্ম", "Properties of Matter"),
                    ("পর্যাবৃত্ত গতি", "Periodic Motion"),
                    ("তরঙ্গ", "Waves"),
                    ("আদর্শ গ্যাস ও গ্যাসের গতিতত্ত্ব", "Ideal Gas and Kinetic Theory"),
                ]
            },
            "Physics 2nd Paper": {
                "name_bn": "পদার্থবিজ্ঞান ২য় পত্র",
                "chapters": [
                    ("তাপগতিবিদ্যা", "Thermodynamics"),
                    ("স্থির তড়িৎ", "Static Electricity"),
                    ("চল তড়িৎ", "Current Electricity"),
                    ("তড়িৎ প্রবাহের চৌম্বক ক্রিয়া ও চুম্বকত্ব", "Magnetic Effect of Current and Magnetism"),
                    ("তাড়িতচৌম্বকীয় আবেশ ও পরিবর্তী প্রবাহ", "Electromagnetic Induction and AC"),
                    ("জ্যামিতিক আলোকবিজ্ঞান", "Geometric Optics"),
                    ("ভৌত আলোকবিজ্ঞান", "Physical Optics"),
                    ("আধুনিক পদার্থবিজ্ঞানের সূচনা", "Introduction to Modern Physics"),
                    ("পরমাণুর মডেল ও নিউক্লিয়ার পদার্থবিজ্ঞান", "Atomic Model and Nuclear Physics"),
                    ("সেমিকন্ডাক্টর ও ইলেকট্রনিক্স", "Semiconductor and Electronics"),
                ]
            },
            "Chemistry 1st Paper": {
                "name_bn": "রসায়ন ১ম পত্র",
                "chapters": [
                    ("ল্যাবরেটরির নিরাপদ ব্যবহার", "Safe Use of Laboratory"),
                    ("গুণগত রসায়ন", "Qualitative Chemistry"),
                    ("মৌলের পর্যায়বৃত্ত ধর্ম ও রাসায়নিক বন্ধন", "Periodic Properties and Chemical Bonding"),
                    ("রাসায়নিক পরিবর্তন", "Chemical Changes"),
                    ("কর্মমুখী রসায়ন", "Applied Chemistry"),
                    ("পরিমাণগত রসায়ন", "Quantitative Chemistry"),
                    ("তড়িৎ রসায়ন", "Electrochemistry"),
                    ("অর্থনৈতিক রসায়ন", "Economic Chemistry"),
                ]
            },
            "Chemistry 2nd Paper": {
                "name_bn": "রসায়ন ২য় পত্র",
                "chapters": [
                    ("পরিবেশ রসায়ন", "Environmental Chemistry"),
                    ("জৈব রসায়ন", "Organic Chemistry"),
                    ("হাইড্রোকার্বন", "Hydrocarbons"),
                    ("অ্যালকোহল, ফেনল ও ইথার", "Alcohol, Phenol and Ether"),
                    ("অ্যালডিহাইড ও কিটোন", "Aldehyde and Ketone"),
                    ("কার্বক্সিলিক এসিড", "Carboxylic Acid"),
                    ("জৈব নাইট্রোজেন যৌগ", "Organic Nitrogen Compounds"),
                    ("পলিমার", "Polymers"),
                    ("জৈব রসায়নে গুরুত্বপূর্ণ যৌগ", "Important Compounds in Biochemistry"),
                ]
            },
            "Biology 1st Paper": {
                "name_bn": "জীববিজ্ঞান ১ম পত্র",
                "chapters": [
                    ("কোষ ও এর গঠন", "Cell and Its Structure"),
                    ("কোষ বিভাজন", "Cell Division"),
                    ("কোষ রসায়ন", "Cell Chemistry"),
                    ("অণুজীব", "Microorganisms"),
                    ("শৈবাল ও ছত্রাক", "Algae and Fungi"),
                    ("ব্রায়োফাইটা ও টেরিডোফাইটা", "Bryophyta and Pteridophyta"),
                    ("নগ্নবীজী ও আবৃতবীজী উদ্ভিদ", "Gymnosperms and Angiosperms"),
                    ("টিস্যু ও টিস্যুতন্ত্র", "Tissue and Tissue System"),
                    ("উদ্ভিদ শারীরতত্ত্ব", "Plant Physiology"),
                    ("উদ্ভিদ প্রজনন", "Plant Reproduction"),
                ]
            },
            "Biology 2nd Paper": {
                "name_bn": "জীববিজ্ঞান ২য় পত্র",
                "chapters": [
                    ("প্রাণীর বৈচিত্র্য", "Animal Diversity"),
                    ("প্রাণীর পরিচিতি", "Introduction to Animals"),
                    ("মানব শারীরতত্ত্ব: পরিপাক ও শোষণ", "Human Physiology: Digestion and Absorption"),
                    ("মানব শারীরতত্ত্ব: রক্ত ও সংবহন", "Human Physiology: Blood and Circulation"),
                    ("মানব শারীরতত্ত্ব: শ্বসন ও শ্বাসক্রিয়া", "Human Physiology: Respiration"),
                    ("মানব শারীরতত্ত্ব: রেচন ও অভিস্রবণ নিয়ন্ত্রণ", "Human Physiology: Excretion"),
                    ("মানব শারীরতত্ত্ব: চলন ও অঙ্গ সঞ্চালন", "Human Physiology: Locomotion"),
                    ("মানব শারীরতত্ত্ব: সমন্বয় ও নিয়ন্ত্রণ", "Human Physiology: Coordination"),
                    ("মানব জীবনের ধারাবাহিকতা", "Continuity of Human Life"),
                    ("জীনতত্ত্ব ও বিবর্তন", "Genetics and Evolution"),
                ]
            },
            "Higher Mathematics 1st Paper": {
                "name_bn": "উচ্চতর গণিত ১ম পত্র",
                "chapters": [
                    ("ম্যাট্রিক্স ও নির্ণায়ক", "Matrix and Determinant"),
                    ("সরলরেখা", "Straight Line"),
                    ("বৃত্ত", "Circle"),
                    ("কনিক", "Conics"),
                    ("বিপরীত ত্রিকোণমিতিক ফাংশন", "Inverse Trigonometric Functions"),
                    ("ত্রিকোণমিতিক সমীকরণ", "Trigonometric Equations"),
                    ("অসীম ধারা", "Infinite Series"),
                    ("সীমা ও অন্তরকলন", "Limit and Differentiation"),
                ]
            },
            "Higher Mathematics 2nd Paper": {
                "name_bn": "উচ্চতর গণিত ২য় পত্র",
                "chapters": [
                    ("অন্তরীকরণ", "Differentiation"),
                    ("অন্তরকলের প্রয়োগ", "Application of Differentiation"),
                    ("যোগজীকরণ", "Integration"),
                    ("যোগজীকরণের প্রয়োগ", "Application of Integration"),
                    ("স্থিতিবিদ্যা", "Statics"),
                    ("গতিবিদ্যা", "Dynamics"),
                    ("বিন্যাস ও সমাবেশ", "Permutation and Combination"),
                    ("সম্ভাবনা", "Probability"),
                    ("পরিসংখ্যান", "Statistics"),
                ]
            },
            "ICT": {
                "name_bn": "তথ্য ও যোগাযোগ প্রযুক্তি",
                "chapters": [
                    ("তথ্য ও যোগাযোগ প্রযুক্তি: বিশ্ব ও বাংলাদেশ প্রেক্ষিত", "ICT: World and Bangladesh Perspective"),
                    ("কমিউনিকেশন সিস্টেমস ও নেটওয়ার্কিং", "Communication Systems and Networking"),
                    ("সংখ্যা পদ্ধতি ও ডিজিটাল ডিভাইস", "Number System and Digital Devices"),
                    ("ওয়েব ডিজাইন পরিচিতি ও HTML", "Web Design and HTML"),
                    ("প্রোগ্রামিং ভাষা", "Programming Language"),
                    ("ডেটাবেজ ম্যানেজমেন্ট সিস্টেম", "Database Management System"),
                ]
            },
            "Accounting 1st Paper": {
                "name_bn": "হিসাববিজ্ঞান ১ম পত্র",
                "chapters": [
                    ("হিসাববিজ্ঞান পরিচিতি", "Introduction to Accounting"),
                    ("লেনদেন ও হিসাব সমীকরণ", "Transaction and Accounting Equation"),
                    ("দুতরফা দাখিলা পদ্ধতি", "Double Entry System"),
                    ("জাবেদা", "Journal"),
                    ("খতিয়ান", "Ledger"),
                    ("নগদান বই", "Cash Book"),
                    ("রেওয়ামিল", "Trial Balance"),
                    ("সমন্বয় দাখিলা", "Adjusting Entries"),
                    ("কার্যপত্র", "Worksheet"),
                    ("আর্থিক বিবরণী", "Financial Statements"),
                ]
            },
            "Accounting 2nd Paper": {
                "name_bn": "হিসাববিজ্ঞান ২য় পত্র",
                "chapters": [
                    ("অংশীদারি ব্যবসায়ের হিসাব", "Partnership Accounting"),
                    ("অংশীদারের সুদ ও বেতন", "Partner's Interest and Salary"),
                    ("অংশীদারের পরিবর্তন", "Change in Partnership"),
                    ("যৌথ মূলধন কোম্পানি", "Joint Stock Company"),
                    ("শেয়ার মূলধন", "Share Capital"),
                    ("ঋণপত্র", "Debenture"),
                    ("কোম্পানির আর্থিক বিবরণী", "Company Financial Statements"),
                    ("নির্মাণ হিসাব", "Manufacturing Account"),
                    ("উৎপাদন ব্যয় বিবরণী", "Cost Statement"),
                    ("অনুপাত বিশ্লেষণ", "Ratio Analysis"),
                ]
            },
            "Economics 1st Paper": {
                "name_bn": "অর্থনীতি ১ম পত্র",
                "chapters": [
                    ("মৌলিক অর্থনৈতিক সমস্যা ও এর সমাধান", "Basic Economic Problems and Solutions"),
                    ("ভোক্তা ও উৎপাদকের আচরণ", "Consumer and Producer Behavior"),
                    ("উপযোগ ও চাহিদা", "Utility and Demand"),
                    ("উৎপাদন, উৎপাদন ব্যয় ও আয়", "Production, Cost and Revenue"),
                    ("বাজার", "Market"),
                    ("জাতীয় আয়", "National Income"),
                    ("মুদ্রা ও ব্যাংক", "Money and Bank"),
                    ("সরকারি অর্থব্যবস্থা", "Public Finance"),
                ]
            },
            "Economics 2nd Paper": {
                "name_bn": "অর্থনীতি ২য় পত্র",
                "chapters": [
                    ("বাংলাদেশের অর্থনীতি পরিচয়", "Introduction to Bangladesh Economy"),
                    ("বাংলাদেশের কৃষি", "Agriculture of Bangladesh"),
                    ("বাংলাদেশের শিল্প", "Industry of Bangladesh"),
                    ("জনসংখ্যা, মানবসম্পদ ও আত্মকর্মসংস্থান", "Population, Human Resource and Self-employment"),
                    ("খাদ্য নিরাপত্তা", "Food Security"),
                    ("বাংলাদেশের বৈদেশিক বাণিজ্য", "Foreign Trade of Bangladesh"),
                    ("সামষ্টিক অর্থনীতি: অর্থ ও ব্যাংক ব্যবস্থা", "Macro Economy: Money and Banking"),
                    ("উন্নয়ন পরিকল্পনা ও বাজেট", "Development Planning and Budget"),
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
        updated_classes = 0
        created_subjects = 0
        updated_subjects = 0
        created_chapters = 0
        updated_chapters = 0

        for class_num, class_data in NCTB_DATA.items():
            # Check if class already exists
            existing_class = Class.query.filter_by(name=class_data["name"]).first()
            if existing_class:
                # Update existing class
                existing_class.name_bn = class_data["name_bn"]
                existing_class.level = class_data["level"]
                existing_class.order = class_num
                cls = existing_class
                updated_classes += 1
                print(f"↻ Updated class: {class_data['name']} ({class_data['name_bn']})")
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

            # Add/Update subjects
            for subj_name, subj_data in class_data["subjects"].items():
                existing_subject = Subject.query.filter_by(
                    name=subj_name, class_id=cls.id
                ).first()
                
                if existing_subject:
                    # Update existing subject
                    existing_subject.name_bn = subj_data["name_bn"]
                    existing_subject.order = list(class_data["subjects"].keys()).index(subj_name) + 1
                    subj = existing_subject
                    updated_subjects += 1
                    print(f"  ↻ Updated subject: {subj_name} ({subj_data['name_bn']})")
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
                    print(f"  ✓ Created subject: {subj_name} ({subj_data['name_bn']})")

                # Add/Update chapters
                for idx, (chap_bn, chap_en) in enumerate(subj_data["chapters"], 1):
                    existing_chapter = Chapter.query.filter_by(
                        chapter_number=idx, subject_id=subj.id
                    ).first()
                    
                    if existing_chapter:
                        # Update existing chapter
                        existing_chapter.name = chap_en
                        existing_chapter.name_bn = chap_bn
                        existing_chapter.order = idx
                        updated_chapters += 1
                    else:
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
        print(f"  Classes created:  {created_classes} | updated: {updated_classes}")
        print(f"  Subjects created: {created_subjects} | updated: {updated_subjects}")
        print(f"  Chapters created: {created_chapters} | updated: {updated_chapters}")
        print("=" * 50)


if __name__ == "__main__":
    seed_nctb()
