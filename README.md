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

## Authentication Requirements

When launching this MCP in an orchestration tool, you will need the following authentication tokens configured as environment variables:

### Required Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `WITHINGS_CLIENT_ID` | Yes | Your Withings Developer App Client ID |
| `WITHINGS_CLIENT_SECRET` | Yes | Your Withings Developer App Client Secret |
| `WITHINGS_ACCESS_TOKEN` | Yes | OAuth2 access token for Withings API |
| `WITHINGS_REFRESH_TOKEN` | Optional | OAuth2 refresh token for automatic token renewal (tokens will need manual renewal if not provided) |
| `ENCRYPTION_KEY` | Yes (for DB storage) | Fernet encryption key for secure token storage |
| `DATABASE_URL` | Optional | Database connection string (defaults to SQLite) |
| `BASE_URL` | Optional | Base URL of your deployed service |

### How to Obtain Tokens

1. **Create a Withings Developer App**: Register at [Withings Developer Portal](https://developer.withings.com/) to get your `WITHINGS_CLIENT_ID` and `WITHINGS_CLIENT_SECRET`.

2. **Get Access Token via OAuth Flow**:
   - Start the server and visit `/auth/withings` to initiate the OAuth flow
   - After authorization, you'll receive the access and refresh tokens
   - Set these as `WITHINGS_ACCESS_TOKEN` and `WITHINGS_REFRESH_TOKEN` in your environment

3. **For Orchestration Tools**: Configure these environment variables in your orchestration tool's settings before launching the MCP.

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