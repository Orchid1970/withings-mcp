# Withings MCP Token Refresh Guide

## Overview

This guide documents the automated token refresh system for the Withings MCP integration.

### Token Lifecycle

| Token Type | Lifetime | Rotation |
|------------|----------|----------|
| Access Token | ~14 days (1,209,600 seconds) | Refreshed via refresh token |
| Refresh Token | ~6 months* | May rotate on each use |

*After ~6 months of inactivity, full user re-authorization is required.

---

## Quick Start

### Automated Refresh (Recommended)

The MCP server automatically handles token refresh. To manually trigger:

```bash
# Via API endpoint (requires admin token)
curl -X POST https://withings-mcp-production.up.railway.app/admin/token/refresh \
  -H "X-Admin-Token: YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"update_railway": true, "trigger_deployment": false}'
```

### Manual Refresh Script

```bash
# Using environment variables
python scripts/manual_refresh.py

# Output in .env format
python scripts/manual_refresh.py --output-env

# Skip Railway update
python scripts/manual_refresh.py --no-railway
```

---

## Configuration

### Required Environment Variables

```bash
# Withings OAuth (Required)
WITHINGS_CLIENT_ID=your_client_id
WITHINGS_CLIENT_SECRET=your_client_secret
WITHINGS_REFRESH_TOKEN=your_refresh_token
WITHINGS_ACCESS_TOKEN=your_access_token

# Token Metadata (Auto-managed)
WITHINGS_TOKEN_EXPIRES_AT=2025-01-15T12:00:00Z
WITHINGS_TOKEN_LAST_REFRESHED=2025-01-01T12:00:00Z

# Railway Integration (Optional)
RAILWAY_API_TOKEN=your_railway_token
RAILWAY_PROJECT_ID=your_project_id
RAILWAY_SERVICE_ID=your_service_id

# Admin Access (Required in production)
ADMIN_API_TOKEN=your_admin_token
```

### Simtheory.ai Integration

The MCP is configured via `simtheory-mcp-config.json`:

```json
{
  "name": "withings-mcp",
  "version": "1.0.0",
  "description": "Timothy's health optimization tracking",
  "transport": {
    "type": "http",
    "url": "https://withings-mcp-production.up.railway.app/mcp"
  }
}
```

---

## API Endpoints

### Admin Endpoints

All admin endpoints require the `X-Admin-Token` header.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/admin/health` | GET | Health check (no auth required) |
| `/admin/token/status` | GET | Current token status |
| `/admin/token/refresh` | POST | Trigger token refresh |
| `/admin/authorization-url` | GET | Get OAuth authorization URL |
| `/admin/token/exchange` | POST | Exchange auth code for tokens |

### Example: Check Token Status

```bash
curl https://withings-mcp-production.up.railway.app/admin/token/status \
  -H "X-Admin-Token: YOUR_ADMIN_TOKEN"
```

Response:
```json
{
  "token_configured": true,
  "expires_at": "2025-01-15T12:00:00Z",
  "expires_in_hours": 240.5,
  "should_refresh": false,
  "next_refresh_recommended": "2025-01-14T12:00:00Z",
  "last_refreshed": "2025-01-01T12:00:00Z"
}
```

---

## OAuth Flow

### Initial Authorization

1. **Get Authorization URL**
   ```bash
   curl https://withings-mcp-production.up.railway.app/admin/authorization-url \
     -H "X-Admin-Token: YOUR_ADMIN_TOKEN"
   ```

2. **User Authorizes**
   - Open the returned URL in a browser
   - Log in to Withings
   - Authorize the application
   - User is redirected to callback URL with `code` parameter

3. **Exchange Code for Tokens**
   ```bash
   curl -X POST "https://withings-mcp-production.up.railway.app/admin/token/exchange?code=AUTH_CODE" \
     -H "X-Admin-Token: YOUR_ADMIN_TOKEN"
   ```

### Token Refresh

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   MCP Server    │     │   Withings API  │     │    Railway      │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         │  POST /oauth2         │                       │
         │  grant_type=refresh   │                       │
         │───────────────────────>                       │
         │                       │                       │
         │  {access_token,       │                       │
         │   refresh_token,      │                       │
         │   expires_in}         │                       │
         │<───────────────────────                       │
         │                       │                       │
         │                       │  Update env vars      │
         │───────────────────────────────────────────────>
         │                       │                       │
         │                       │  Success              │
         │<───────────────────────────────────────────────
         │                       │                       │
```

---

## Error Handling

### Error Codes

| Status | Code | Description | Action |
|--------|------|-------------|--------|
| 0 | SUCCESS | Token refreshed | Store new tokens |
| 26 | INVALID_REFRESH_TOKEN | Token expired/revoked | Re-authorize user |
| 29 | INVALID_CODE | Bad authorization code | Request new code |

### Recovery Procedures

#### Refresh Token Expired

```bash
# 1. Get new authorization URL
curl https://withings-mcp-production.up.railway.app/admin/authorization-url \
  -H "X-Admin-Token: YOUR_ADMIN_TOKEN"

# 2. Complete OAuth flow in browser
# 3. Exchange the new authorization code
```

#### Railway Update Failed

Manually update via Railway CLI:

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link to project
railway link

# Update variables
railway variables set WITHINGS_ACCESS_TOKEN="new_token"
railway variables set WITHINGS_REFRESH_TOKEN="new_refresh_token"
railway variables set WITHINGS_TOKEN_EXPIRES_AT="2025-01-15T12:00:00Z"

# Redeploy
railway up
```

---

## Security Considerations

### Token Protection

- ✅ Never log actual token values (use masked format: `token_*****xyz`)
- ✅ All API calls use HTTPS
- ✅ Tokens stored only in Railway environment variables (not in code/repo)
- ✅ Admin endpoints protected with API token
- ✅ Refresh tokens rotated on each use (per Withings recommendation)

### Masking Format

All token values are logged in masked format:
```
token_*****xyz
```

Where `xyz` are the last 3 characters of the token.

---

## Monitoring

### Health Check

```bash
curl https://withings-mcp-production.up.railway.app/admin/health
```

### Log Format (JSON)

```json
{
  "timestamp": "2025-01-01T12:00:00.000Z",
  "level": "INFO",
  "logger": "app.services.token_refresh",
  "service": "withings-mcp",
  "environment": "production",
  "message": "Token refresh successful. Expires at: 2025-01-15T12:00:00Z"
}
```

### Recommended Monitoring

1. **Proactive Refresh**: Schedule refresh 24 hours before expiration
2. **Alert on Failure**: Monitor for `INVALID_REFRESH_TOKEN` status
3. **Track Expiration**: Log `WITHINGS_TOKEN_EXPIRES_AT` for tracking

---

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| "INVALID_REFRESH_TOKEN" | Token expired after 6 months | Re-authorize user |
| "CONFIGURATION_ERROR" | Missing env vars | Check Railway variables |
| "NETWORK_ERROR" | Withings API timeout | Retry after 30 seconds |
| Railway update failed | Invalid API token | Regenerate RAILWAY_API_TOKEN |

### Debug Commands

```bash
# Check current configuration (local)
python -c "import os; print(f'Client ID: {os.getenv(\"WITHINGS_CLIENT_ID\", \"NOT SET\")[:8]}...')"

# Test token refresh (dry run)
python scripts/manual_refresh.py --no-railway --output-env

# Check Railway deployment status
railway status
```

---

## References

- [Withings OAuth 2.0 Documentation](https://developer.withings.com/developer-guide/v3/integration-guide/dropship-cellular/get-access/access-and-refresh-tokens/)
- [Railway Environment Variables](https://docs.railway.app/develop/variables)
- [MCP Protocol Specification](https://github.com/modelcontextprotocol)
- [Simtheory.ai MCP Integration](https://simtheory.ai)
