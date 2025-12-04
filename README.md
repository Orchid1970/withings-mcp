# Withings MCP

**Health Data Orchestrator** - A FastAPI service that connects to Withings, ingests health data, and normalizes it to FHIR-like Observations. 

## Features

- OAuth2 flow for Withings authentication
- Automatic token refresh
- FHIR-compliant data normalization (LOINC codes)
- Background sync scheduler (every 2 hours)
- Encrypted token storage
- SQLite (dev) / PostgreSQL (prod) support
- Docker-ready with Railway & Render configs

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/Orchid1970/withings-mcp.git
cd withings-mcp
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your Withings credentials
```

Generate an encryption key:
```python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

### 3. Run Locally

```bash
uvicorn src.app:api --reload --host 0.0.0.0 --port 8000
```

### 4. Deploy to Railway

```bash
npm install -g @railway/cli
railway login
railway init
railway up
```

Then set environment variables in Railway dashboard.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/auth/withings` | GET | Start OAuth flow |
| `/auth/withings/callback` | GET | OAuth callback |
| `/workflows/withings/sync` | POST | Trigger manual sync |
| `/workflows/withings/observations` | GET | Get stored observations |

## FHIR Mappings

Withings measurements are mapped to LOINC codes:

| Withings | LOINC | Description |
|----------|-------|-------------|
| 1 | 29463-7 | Body weight |
| 10 | 8480-6 | Systolic BP |
| 11 | 8462-4 | Diastolic BP |
| 12 | 8867-4 | Heart rate |
| ... | ... | See `src/fhir_mappings.py` |

## License

MIT
