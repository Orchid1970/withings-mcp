#!/usr/bin/env python3
"""
Manual Token Refresh Script
============================
Fallback script for manually refreshing Withings tokens when automated
refresh fails or browser automation is unavailable.

Usage:
    # Using environment variables:
    python scripts/manual_refresh.py
    
    # With explicit refresh token:
    python scripts/manual_refresh.py --refresh-token YOUR_REFRESH_TOKEN
    
    # Skip Railway update:
    python scripts/manual_refresh.py --no-railway

Requirements:
    - WITHINGS_CLIENT_ID env var
    - WITHINGS_CLIENT_SECRET env var
    - WITHINGS_REFRESH_TOKEN env var (or --refresh-token argument)
    - RAILWAY_API_TOKEN env var (for Railway updates)
    - RAILWAY_PROJECT_ID env var (for Railway updates)
    - RAILWAY_SERVICE_ID env var (for Railway updates)
"""

import os
import sys
import asyncio
import argparse
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load .env file if present (for local development)
try:
    from dotenv import load_dotenv
    load_dotenv(project_root / '.env')
except ImportError:
    pass

from app.services.token_refresh import (
    WithingsTokenRefreshService,
    TokenRefreshStatus
)
from app.services.railway_client import RailwayClient


def mask_token(token: str) -> str:
    """Mask token for display."""
    if not token or len(token) < 10:
        return "[MASKED]" if token else "[NONE]"
    return f"token_*****{token[-3:]}"


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{'='*60}")
    print(f" {text}")
    print(f"{'='*60}\n")


def print_step(step: int, text: str):
    """Print a step indicator."""
    print(f"\n[Step {step}] {text}")
    print("-" * 40)


def print_success(text: str):
    """Print success message."""
    print(f"✅ {text}")


def print_error(text: str):
    """Print error message."""
    print(f"❌ {text}")


def print_warning(text: str):
    """Print warning message."""
    print(f"⚠️  {text}")


def print_info(text: str):
    """Print info message."""
    print(f"ℹ️  {text}")


async def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Manually refresh Withings OAuth tokens"
    )
    parser.add_argument(
        "--refresh-token",
        help="Refresh token to use (defaults to WITHINGS_REFRESH_TOKEN env var)"
    )
    parser.add_argument(
        "--no-railway",
        action="store_true",
        help="Skip Railway environment variable update"
    )
    parser.add_argument(
        "--trigger-deploy",
        action="store_true",
        help="Trigger Railway deployment after updating variables"
    )
    parser.add_argument(
        "--output-env",
        action="store_true",
        help="Output new tokens in .env format for manual configuration"
    )
    
    args = parser.parse_args()
    
    print_header("Withings MCP Token Refresh")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    
    # Validate configuration
    print_step(1, "Validating configuration")
    
    client_id = os.getenv("WITHINGS_CLIENT_ID")
    client_secret = os.getenv("WITHINGS_CLIENT_SECRET")
    refresh_token = args.refresh_token or os.getenv("WITHINGS_REFRESH_TOKEN")
    
    config_valid = True
    
    if client_id:
        print_success(f"WITHINGS_CLIENT_ID: {client_id[:8]}...")
    else:
        print_error("WITHINGS_CLIENT_ID not set")
        config_valid = False
    
    if client_secret:
        print_success(f"WITHINGS_CLIENT_SECRET: {mask_token(client_secret)}")
    else:
        print_error("WITHINGS_CLIENT_SECRET not set")
        config_valid = False
    
    if refresh_token:
        print_success(f"Refresh token: {mask_token(refresh_token)}")
    else:
        print_error("No refresh token available")
        config_valid = False
    
    if not config_valid:
        print_error("\nConfiguration incomplete. Please set required environment variables.")
        print_info("\nRequired variables:")
        print("  - WITHINGS_CLIENT_ID")
        print("  - WITHINGS_CLIENT_SECRET")
        print("  - WITHINGS_REFRESH_TOKEN (or use --refresh-token argument)")
        sys.exit(1)
    
    # Refresh token
    print_step(2, "Refreshing Withings access token")
    
    token_service = WithingsTokenRefreshService(
        client_id=client_id,
        client_secret=client_secret
    )
    
    result = await token_service.refresh_token(refresh_token)
    
    if not result.is_success:
        print_error(f"Token refresh failed: {result.status.value}")
        print_error(f"Error: {result.error_message}")
        
        if result.requires_reauthorization:
            print_warning("\nThe refresh token has expired or been revoked.")
            print_info("You need to re-authorize the application.")
            print(f"\nAuthorization URL:\n{token_service.get_authorization_url()}")
            print("\nSteps:")
            print("1. Open the URL above in a browser")
            print("2. Log in to Withings and authorize the application")
            print("3. Copy the authorization code from the redirect URL")
            print("4. Run this script again with the new code")
        
        sys.exit(1)
    
    print_success("Token refresh successful!")
    print(f"  Access token: {mask_token(result.access_token)}")
    print(f"  Refresh token: {mask_token(result.refresh_token)}")
    print(f"  Expires at: {result.expires_at.isoformat() if result.expires_at else 'Unknown'}")
    print(f"  User ID: {result.user_id}")
    
    # Calculate next refresh time
    next_refresh = token_service.get_next_refresh_time(result.expires_at)
    print(f"  Next refresh recommended: {next_refresh.isoformat()}")
    
    # Output env format if requested
    if args.output_env:
        print_step(3, "Environment variable format")
        print("\n# Add these to your .env file or Railway variables:")
        print(f"WITHINGS_ACCESS_TOKEN={result.access_token}")
        print(f"WITHINGS_REFRESH_TOKEN={result.refresh_token}")
        print(f"WITHINGS_TOKEN_EXPIRES_AT={result.expires_at.isoformat() if result.expires_at else ''}")
        print(f"WITHINGS_TOKEN_LAST_REFRESHED={datetime.now(timezone.utc).isoformat()}")
    
    # Update Railway (if not skipped)
    if not args.no_railway:
        print_step(4 if args.output_env else 3, "Updating Railway environment variables")
        
        railway_token = os.getenv("RAILWAY_API_TOKEN")
        railway_project = os.getenv("RAILWAY_PROJECT_ID")
        railway_service = os.getenv("RAILWAY_SERVICE_ID")
        
        if not all([railway_token, railway_project, railway_service]):
            print_warning("Railway configuration incomplete. Skipping Railway update.")
            print_info("\nTo enable Railway updates, set:")
            print("  - RAILWAY_API_TOKEN")
            print("  - RAILWAY_PROJECT_ID")
            print("  - RAILWAY_SERVICE_ID")
        else:
            railway_client = RailwayClient(
                api_token=railway_token,
                project_id=railway_project,
                service_id=railway_service
            )
            
            railway_result = await railway_client.update_environment_variables(
                access_token=result.access_token,
                refresh_token=result.refresh_token,
                expires_at=result.expires_at
            )
            
            if railway_result.is_success:
                print_success("Railway variables updated successfully!")
                print(f"  Variables updated: {', '.join(railway_result.variables_updated)}")
                
                # Trigger deployment if requested
                if args.trigger_deploy:
                    print_info("\nTriggering Railway deployment...")
                    deploy_result = await railway_client.trigger_deployment()
                    if deploy_result.deployment_id:
                        print_success(f"Deployment triggered: {deploy_result.deployment_id}")
                    else:
                        print_warning(f"Deployment status: {deploy_result.status.value}")
            else:
                print_error(f"Railway update failed: {railway_result.error_message}")
                print_info("You may need to manually update Railway environment variables.")
    
    # Summary
    print_header("Execution Summary")
    print_success(f"Token refresh completed at {datetime.now(timezone.utc).isoformat()}")
    print(f"  New token expires: {result.expires_at.isoformat() if result.expires_at else 'Unknown'}")
    print(f"  Recommended next refresh: {next_refresh.isoformat()}")
    
    if not args.no_railway and os.getenv("RAILWAY_API_TOKEN"):
        print("  Railway variables: Updated")
        if args.trigger_deploy:
            print("  Railway deployment: Triggered")
    else:
        print("  Railway variables: Skipped (use --no-railway=false to enable)")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    asyncio.run(main())
