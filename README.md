# Withings MCP

**Health Data Orchestrator** - A FastAPI service that connects to Withings, ingests health data, and normalizes it to FHIR-like Observations.

## Token Requirements

**Yes, you need tokens to run this MCP.** Here's what you need:

### Required Credentials

1. **Withings API Credentials** (Required before first run):
   - `WITHINGS_CLIENT_ID` - Your Withings application Client ID
   - `WITHINGS_CLIENT_SECRET` - Your Withings application Client Secret
   
   **How to obtain**: Register as a developer at the [Withings Developer Portal](https://developer.withings.com/) and create an application to get these credentials.

2. **Encryption Key** (Required):
   - `ENCRYPTION_KEY` - A Fernet encryption key for secure token storage
   
   **How to generate**: See the "Configure Environment" section below.

### OAuth Tokens (Automatically Generated)

- `WITHINGS_ACCESS_TOKEN` and `WITHINGS_REFRESH_TOKEN` are **automatically obtained** through the OAuth flow when you visit `/auth/withings` endpoint. You don't need to provide these manually.

### Optional Configuration

- `DATABASE_URL` - Defaults to SQLite for local development
- `BASE_URL` - Your application's public URL (important for OAuth callback)

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