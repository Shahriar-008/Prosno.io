Render deployment notes — Prosno.io (WeasyPrint-ready Docker image)

Overview
--------
This project generates Bengali MCQ papers and can produce PDFs with correct
complex-script shaping via WeasyPrint (HTML → PDF). WeasyPrint needs native
libraries (Cairo/Pango/GDK) which are installed in the Docker image below.

Dockerfile (provided)
----------------------
The repository includes `Dockerfile` which:
- uses `python:3.11-slim` as base
- installs system packages: `libcairo2`, `libpango-1.0-0`, `libgdk-pixbuf2.0-0`,
  `libffi-dev`, `shared-mime-info`, and `fonts-noto` — these satisfy WeasyPrint's
  native requirements.
- installs Python dependencies from `requirements.txt` (make sure `weasyprint`
  is present there).

Render (DigitalOcean) — Steps
-----------------------------
1. Push your repository to GitHub.
2. On Render dashboard, create a new **Web Service**.
3. Select **Docker** as the environment and connect your GitHub repo.
4. Set the build and start commands (the Dockerfile handles runtime):
   - No build command needed; Render will build the Docker image from the Dockerfile.
5. Set environment variables (production secrets) in Render:
   - `SECRET_KEY`, `DATABASE_URL` (if using Postgres), etc.
6. Deploy. Render will build the Docker image and run `gunicorn run:app`.

Caveats & Recommendations
-------------------------
- Free tier may be memory-constrained. WeasyPrint/Cairo can spike memory while
  rendering complex pages. For heavy loads consider a paid plan or offloading
  PDF generation to a background worker (e.g., Render Background Worker service).
- Ensure `app/static/fonts/NotoSansBengali-*.ttf` is in the repo so the HTML
  template can use local @font-face paths.
- Test rendering locally before pushing:

  docker build -t prosno:local .
  docker run --rm -p 8000:8000 prosno:local

  Then visit http://localhost:8000

Quick Docker test (generate a sample PDF inside container)
------------------------------------------------------
Use the provided helper to build the image and run a one-off container that
creates `output/test_paper_docker.pdf` on your host:

  bash scripts/docker_test.sh

This runs the `bin/generate_sample_pdf.py` script inside the image and writes
the produced PDF into the repository `output/` directory.

Local dev notes (Windows)
-------------------------
If you prefer to test without Docker on Windows, use conda to get WeasyPrint's
native deps:

  conda create -n prosno python=3.11
  conda activate prosno
  conda install -c conda-forge weasyprint
  pip install -r requirements.txt

Then run the app with your virtualenv Python.
