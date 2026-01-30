# Prosno.io 📝

A modern Flask-based web application for generating professional MCQ question papers. Built with Python, Flask, and python-docx.

![Prosno.io](https://img.shields.io/badge/Flask-3.0-green) ![Python](https://img.shields.io/badge/Python-3.8+-blue) ![License](https://img.shields.io/badge/License-MIT-yellow)

## ✨ Features

- **Modern Landing Page** - Beautiful, responsive design with gradient effects
- **Question Bank Management** - Organize questions by Class, Subject, and Chapter
- **Professional Document Output** - Two-column layout with Bengali numeral support
- **Dual Copy Generation** - Student copy (clean) and Teacher copy (with answers)
- **OMR-Style Options** - Answer choices in 2x2 grid with OMR circles
- **Secure Admin Panel** - Protected backend for managing content
- **Bulk Upload** - Import questions via JSON format
- **Bengali Language Support** - Full Bengali text and numeral rendering

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

### Installation

1. **Clone the repository**
   ```powershell
   git clone https://github.com/yourusername/prosno.io.git
   cd prosno.io
   ```

2. **Create virtual environment**
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

3. **Install dependencies**
   ```powershell
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```powershell
   copy .env.example .env
   # Edit .env with your secret key
   ```

5. **Initialize the database**
   ```powershell
   flask init-db
   ```

6. **Create an admin user**
   ```powershell
   flask create-admin
   ```

7. **Seed demo data (optional)**
   ```powershell
   flask seed-demo
   ```

8. **Run the application**
   ```powershell
   python run.py
   ```

9. **Open your browser**
   - Website: http://localhost:5000
   - Admin Panel: http://localhost:5000/admin

## 📁 Project Structure

```
prosno.io/
├── app/
│   ├── __init__.py          # Application factory
│   ├── models.py             # Database models
│   ├── routes/
│   │   ├── main.py           # Public routes
│   │   ├── admin.py          # Admin routes
│   │   └── api.py            # API endpoints
│   ├── templates/
│   │   ├── base.html         # Base template
│   │   ├── main/             # Public templates
│   │   └── admin/            # Admin templates
│   ├── static/
│   │   ├── css/              # Stylesheets
│   │   └── js/               # JavaScript files
│   └── utils/
│       └── document_generator.py  # DOCX generation
├── config.py                 # Configuration settings
├── run.py                    # Application entry point
├── requirements.txt          # Python dependencies
└── README.md                 # This file
```

## 🎯 Usage

### Generating Question Papers

1. Navigate to the **Generate Paper** page
2. Select a **Class** from the dropdown
3. Choose a **Subject**
4. Select one or more **Chapters**
5. Configure paper settings (title, questions, time)
6. Click **Generate Question Paper**
7. Download both Student and Teacher copies

### Managing Content (Admin)

1. Log in to the admin panel at `/admin`
2. Add Classes, Subjects, and Chapters
3. Add individual questions or bulk upload via JSON
4. View generated papers and download statistics

### JSON Format for Bulk Upload

```json
[
  {
    "question_text": "What is 2 + 2?",
    "type": "simple",
    "answer_options": ["3", "4", "5", "6"],
    "correct_answer": "4"
  },
  {
    "question_text": "Consider the following:",
    "type": "complex",
    "sub_options": ["i. Statement one", "ii. Statement two"],
    "final_prompt": "Which is correct?",
    "answer_options": ["i only", "ii only", "Both", "Neither"],
    "correct_answer": "i only"
  }
]
```

## 🔐 Security Features

- **Password Hashing** - Werkzeug security for password storage
- **CSRF Protection** - Flask-WTF CSRF tokens on all forms
- **Session Management** - Secure Flask-Login sessions
- **SQL Injection Prevention** - SQLAlchemy ORM queries
- **Environment Variables** - Sensitive data in .env file

## 🛠️ Configuration

Edit `config.py` or set environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Flask secret key | Random string |
| `DATABASE_URL` | Database connection URL | SQLite |
| `FLASK_ENV` | Environment mode | development |

## 📦 Dependencies

- **Flask** - Web framework
- **Flask-SQLAlchemy** - Database ORM
- **Flask-Login** - User authentication
- **Flask-WTF** - Form handling & CSRF
- **python-docx** - Word document generation
- **Werkzeug** - Password hashing

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Based on the [question-generation-python-script](https://github.com/Shahriar-008/question-generation-python-script) project
- Bootstrap 5 for UI components
- Bootstrap Icons for iconography

---

Made with ❤️ for educators everywhere
