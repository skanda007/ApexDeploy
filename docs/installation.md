# ApexDeploy — Installation Guide

## Prerequisites

| Requirement | Version | Purpose |
|------------|---------|---------|
| Python | 3.12+ | Runtime |
| Docker Desktop | Latest | Container management |
| Git | 2.40+ | Repository operations |
| Google API Key | — | Gemini LLM access |

---

## Option 1: Local Development

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/apexdeploy.git
cd apexdeploy
```

### 2. Create Virtual Environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and set your `GOOGLE_API_KEY`:
```env
GOOGLE_API_KEY=your-actual-gemini-api-key
```

### 5. Start the Backend

```bash
uvicorn src.main:app --reload --port 8000
```

### 6. Start the Dashboard

Open a new terminal:
```bash
streamlit run dashboard/app.py
```

### 7. Access

- **Dashboard**: http://localhost:8501
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/health

---

## Option 2: Docker Compose

### 1. Configure Environment

```bash
cp .env.example .env
# Edit .env with your GOOGLE_API_KEY
```

### 2. Build & Start

```bash
docker compose up --build
```

### 3. Stop

```bash
docker compose down
```

---

## Obtaining a Google API Key

1. Go to [Google AI Studio](https://aistudio.google.com/)
2. Sign in with your Google account
3. Click "Get API Key" → "Create API Key"
4. Copy the key and paste it into your `.env` file

---

## Troubleshooting

| Issue | Solution |
|-------|---------|
| `ModuleNotFoundError` | Ensure virtual environment is activated |
| Docker connection error | Start Docker Desktop |
| Gemini API error | Verify `GOOGLE_API_KEY` in `.env` |
| Port already in use | Change `API_PORT` or `DASHBOARD_PORT` in `.env` |
