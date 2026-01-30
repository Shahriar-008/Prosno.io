"""
Prosno.io - Question Paper Generator
Main Application Entry Point
"""
from app import create_app, db
from app.models import User, Class, Subject, Chapter, Question

app = create_app()


@app.shell_context_processor
def make_shell_context():
    """Make database models available in Flask shell"""
    return {
        'db': db,
        'User': User,
        'Class': Class,
        'Subject': Subject,
        'Chapter': Chapter,
        'Question': Question
    }


@app.cli.command('init-db')
def init_db():
    """Initialize the database with tables"""
    db.create_all()
    print('Database initialized successfully!')


@app.cli.command('create-admin')
def create_admin():
    """Create an admin user"""
    import getpass
    
    username = input('Username: ')
    email = input('Email: ')
    password = getpass.getpass('Password: ')
    
    if User.query.filter_by(username=username).first():
        print(f'User {username} already exists!')
        return
    
    user = User(username=username, email=email, is_admin=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    
    print(f'Admin user {username} created successfully!')


@app.cli.command('seed-demo')
def seed_demo():
    """Seed database with demo data"""
    # Create demo class
    class8 = Class(
        name='Class 8',
        name_bn='অষ্টম শ্রেণি',
        level='Secondary',
        order=8
    )
    db.session.add(class8)
    db.session.flush()
    
    # Create demo subjects
    bangla = Subject(
        name='Bangla',
        name_bn='বাংলা',
        code='BNG',
        class_id=class8.id,
        order=1
    )
    math = Subject(
        name='Mathematics',
        name_bn='গণিত',
        code='MATH',
        class_id=class8.id,
        order=2
    )
    science = Subject(
        name='General Science',
        name_bn='সাধারণ বিজ্ঞান',
        code='SCI',
        class_id=class8.id,
        order=3
    )
    db.session.add_all([bangla, math, science])
    db.session.flush()
    
    # Create demo chapters
    ch1 = Chapter(name='Algebra', name_bn='বীজগণিত', chapter_number=1, subject_id=math.id, order=1)
    ch2 = Chapter(name='Geometry', name_bn='জ্যামিতি', chapter_number=2, subject_id=math.id, order=2)
    ch3 = Chapter(name='Physics Basics', name_bn='পদার্থবিজ্ঞানের মূলনীতি', chapter_number=1, subject_id=science.id, order=1)
    db.session.add_all([ch1, ch2, ch3])
    db.session.flush()
    
    # Create demo questions
    questions = [
        Question(
            question_text='2 + 2 = ?',
            question_type='simple',
            answer_options=['3', '4', '5', '6'],
            correct_answer='4',
            chapter_id=ch1.id
        ),
        Question(
            question_text='What is the value of x if 2x = 10?',
            question_type='simple',
            answer_options=['3', '4', '5', '6'],
            correct_answer='5',
            chapter_id=ch1.id
        ),
        Question(
            question_text='A triangle has how many sides?',
            question_type='simple',
            answer_options=['2', '3', '4', '5'],
            correct_answer='3',
            chapter_id=ch2.id
        ),
        Question(
            question_text='What is the SI unit of force?',
            question_type='simple',
            answer_options=['Joule', 'Newton', 'Watt', 'Pascal'],
            correct_answer='Newton',
            chapter_id=ch3.id
        ),
        Question(
            question_text='Consider the following statements:',
            question_type='complex',
            sub_options=['i. Light travels in straight lines.', 'ii. Sound travels faster than light.'],
            final_prompt='Which of the above is correct?',
            answer_options=['i only', 'ii only', 'Both i and ii', 'Neither i nor ii'],
            correct_answer='i only',
            chapter_id=ch3.id
        )
    ]
    db.session.add_all(questions)
    db.session.commit()
    
    print('Demo data seeded successfully!')
    print(f'- 1 Class')
    print(f'- 3 Subjects')
    print(f'- 3 Chapters')
    print(f'- 5 Questions')


if __name__ == '__main__':
    app.run(debug=True)
