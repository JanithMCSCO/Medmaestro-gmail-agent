#!/usr/bin/env python3
"""
Headless Gmail Setup Script

This script helps set up Gmail API authentication on servers without GUI/browser access.
"""

import os
import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def setup_gmail_headless():
    """Setup Gmail authentication for headless environments"""
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from config import Config
        
        logger.info("🔧 Setting up Gmail authentication for headless environment...")
        
        # Check if credentials file exists
        if not os.path.exists(Config.GMAIL_CLIENT_SECRET_FILE):
            logger.error(f"❌ Gmail credentials file not found: {Config.GMAIL_CLIENT_SECRET_FILE}")
            logger.info("📋 To fix this:")
            logger.info("1. Go to https://console.cloud.google.com/")
            logger.info("2. Enable Gmail API")
            logger.info("3. Create OAuth 2.0 credentials")
            logger.info("4. Download as 'client_secret.json.json'")
            return False
        
        # Check if we already have a token
        if os.path.exists(Config.GMAIL_TOKEN_FILE):
            logger.info("✅ Gmail token already exists. Testing existing authentication...")
            try:
                from gmail_service import GmailService
                gmail_service = GmailService()
                
                # Test with a simple API call
                messages = gmail_service.get_recent_messages(max_results=1)
                logger.info("✅ Existing Gmail authentication is working!")
                return True
                
            except Exception as e:
                logger.warning(f"⚠️ Existing token invalid: {str(e)}")
                logger.info("🔄 Removing old token and creating new one...")
                os.remove(Config.GMAIL_TOKEN_FILE)
        
        # Create new authentication
        logger.info("🌐 Starting OAuth flow for headless environment...")
        
        flow = InstalledAppFlow.from_client_secrets_file(
            Config.GMAIL_CLIENT_SECRET_FILE, 
            Config.GMAIL_SCOPES
        )
        
        logger.info("🔗 Please follow these steps:")
        logger.info("=" * 60)
        
        # Start the console flow
        creds = flow.run_console()
        
        # Save the credentials
        with open(Config.GMAIL_TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
        
        logger.info("✅ Gmail authentication setup completed!")
        logger.info(f"📁 Token saved to: {Config.GMAIL_TOKEN_FILE}")
        
        # Test the authentication
        logger.info("🧪 Testing the new authentication...")
        from gmail_service import GmailService
        gmail_service = GmailService()
        
        messages = gmail_service.get_recent_messages(max_results=1)
        logger.info("✅ Gmail API test successful!")
        
        return True
        
    except ImportError as e:
        logger.error(f"❌ Missing required library: {str(e)}")
        logger.info("💡 Try: pip install google-auth google-auth-oauthlib google-api-python-client")
        return False
        
    except Exception as e:
        logger.error(f"❌ Gmail setup failed: {str(e)}")
        return False

def check_prerequisites():
    """Check if all prerequisites are met"""
    logger.info("🔍 Checking prerequisites...")
    
    # Check if config can be loaded
    try:
        from config import Config
        logger.info("✅ Configuration loaded successfully")
    except Exception as e:
        logger.error(f"❌ Configuration error: {str(e)}")
        return False
    
    # Check required Python packages
    required_packages = [
        'google.auth',
        'google_auth_oauthlib',
        'googleapiclient'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
            logger.info(f"✅ {package} is available")
        except ImportError:
            missing_packages.append(package)
            logger.error(f"❌ {package} is missing")
    
    if missing_packages:
        logger.error("💡 Install missing packages with:")
        logger.error("   pip install google-auth google-auth-oauthlib google-api-python-client")
        return False
    
    return True

def main():
    logger.info("🚀 Gmail Headless Setup Tool")
    logger.info("=" * 50)
    
    # Check prerequisites first
    if not check_prerequisites():
        logger.error("💥 Prerequisites not met. Please install required packages.")
        sys.exit(1)
    
    print()
    
    # Setup Gmail authentication
    success = setup_gmail_headless()
    
    print()
    logger.info("=" * 50)
    
    if success:
        logger.info("🎉 Gmail setup completed successfully!")
        logger.info("💡 You can now run: python test_gmail.py")
    else:
        logger.error("💥 Gmail setup failed. Please check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main() 