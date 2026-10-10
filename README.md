# Certificate Generator

A fast, modern web application for generating personalized certificates in bulk.

Upload any certificate template (PDF, PNG, JPG, JPEG), import names manually or via Excel/CSV, interactively drag & style the name on a live preview, and download all generated certificates in a single ZIP file.

---

## 🏗️ Architecture & Tech Stack

```text
               GitHub Repository
                       │
       ┌───────────────┴───────────────┐
       ▼                               ▼
    Frontend                        Backend
 (Next.js / Vercel)            (FastAPI / Render)
```

- **Frontend**: Next.js 15, React 19, TypeScript, Tailwind CSS
- **Backend**: Python 3.12, FastAPI, PyMuPDF (fitz), Pillow, pandas, openpyxl
- **Deployment**: Vercel (Frontend) & Render (Backend)

---

## ✨ Core Features

- 📄 **Dynamic Template Upload**: Support for PDF, PNG, JPG, and JPEG files without hardcoded paths.
- 👥 **Flexible Name Input**: Type/paste names line-by-line or upload `.xlsx` / `.csv` spreadsheets (auto-detects `Name` column).
- 🎯 **Interactive Visual Preview**: Drag and position names directly on the live template rendered to scale.
- 🎨 **Text Styling**: Customize font (14 standard PDF fonts), font size, text color, and alignment (left, center, right).
- 📦 **Bulk ZIP Export**: Generates sanitized individual PDFs per recipient and packages them into a `certificates.zip`.
- 🗂️ **Merged PDF Export**: Optionally returns one multi-page `certificates.pdf` with the template stored only once (much smaller for large image templates).
- 🧹 **Zero Storage Overhead**: Per-request temporary scratch spaces with auto-cleanup on request end and background purging of stale workspaces.

---

## 🛠️ Local Development Setup

### 1. Prerequisites

- Python 3.10+
- Node.js 18+ & npm

### 2. Backend Setup (FastAPI)

```bash
# Navigate to backend directory
cd backend

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run the backend server
uvicorn app.main:app --reload --port 8000
```

The API server will run on `http://localhost:8000`. API documentation is available at `http://localhost:8000/docs`.

To run backend tests:
```bash
pytest backend/tests
```

### 3. Frontend Setup (Next.js)

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Create environment file if needed
cp .env.example .env.local

# Run the development server
npm run dev
```

The frontend will run on `http://localhost:3000`.

To build the production bundle:
```bash
npm run build
```

---

## 🌐 Environment Variables

### Frontend (`frontend/.env.local`)
- `NEXT_PUBLIC_API_URL`: Backend API endpoint (e.g. `http://localhost:8000` locally or `https://your-backend.onrender.com` in production).

### Backend Config Options (Optional)
- `CORS_ORIGINS`: Comma-separated extra allowed origins, appended to the built-in allowlist (localhost + the production Vercel URL). It does **not** default to `*`; wildcards are ignored because credentials are enabled. Use `CORS_ORIGIN_REGEX` instead.
- `CORS_ORIGIN_REGEX`: Regular expression of allowed origins, useful for Vercel preview deployments (e.g. `https://.*\.vercel\.app`). Unset by default.
- `MAX_TEMPLATE_SIZE_MB`: Max template upload size (defaults to `25`).
- `MAX_SPREADSHEET_SIZE_MB`: Max Excel/CSV upload size (defaults to `10`).
- `MAX_NAMES`: Max names per bulk generation request (defaults to `2000`).
- `MAX_TOTAL_OUTPUT_MB`: Max estimated size of an individual ZIP export, `template size × names` (defaults to `1024`). Requests over the limit return HTTP 413; the `merged` output mode is not affected.

---

## 🚀 Production Deployment

### Frontend (Vercel)
1. Import the repository in [Vercel](https://vercel.com).
2. Set root directory to `frontend`.
3. Add Environment Variable:
   - `NEXT_PUBLIC_API_URL` = `https://<your-render-app>.onrender.com`
4. Deploy.

### Backend (Render)
1. Create a Web Service on [Render](https://render.com).
2. Set Root Directory to `backend`.
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Deploy.
