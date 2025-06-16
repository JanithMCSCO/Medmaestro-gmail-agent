#!/usr/bin/env python3
"""
Medical Gmail Agent - Main Entry Point

This script provides the main entry point for the medical email processing system.
It can run in different modes:
1. Webhook server mode (for real-time processing)
2. Batch processing mode (for manual/scheduled processing)
3. Setup mode (for initial configuration)
"""

import sys
import argparse
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('medical_gmail_agent.log')
    ]
)
logger = logging.getLogger(__name__)

def setup_gmail_push_notifications():
    """
    Setup Gmail push notifications
    """
    try:
        from gmail_service import GmailService
        from config import Config
        
        gmail_service = GmailService()
        
        if not Config.WEBHOOK_URL:
            logger.error("WEBHOOK_URL not configured. Please set it in your environment variables.")
            return False
        
        success = gmail_service.setup_push_notifications(Config.WEBHOOK_URL)
        if success:
            logger.info("Gmail push notifications setup successfully!")
            logger.info(f"Webhook URL: {Config.WEBHOOK_URL}")
        else:
            logger.error("Failed to setup Gmail push notifications")
        
        return success
        
    except Exception as e:
        logger.error(f"Error setting up push notifications: {str(e)}")
        return False

def run_webhook_server():
    """
    Run the webhook server for real-time email processing
    """
    try:
        from webhook_server import run_server
        logger.info("Starting webhook server for real-time email processing...")
        run_server()
        
    except KeyboardInterrupt:
        logger.info("Webhook server stopped by user")
    except Exception as e:
        logger.error(f"Error running webhook server: {str(e)}")
        sys.exit(1)

def run_batch_processing(days_back: int = 1):
    """
    Run batch processing for recent emails
    """
    try:
        from email_processor import MedicalEmailProcessor
        
        logger.info(f"Starting batch processing for emails from last {days_back} days...")
        
        processor = MedicalEmailProcessor()
        
        # Process recent emails
        result = processor.process_recent_emails(days_back=days_back)
        
        if result['success']:
            logger.info(f"Batch processing completed successfully!")
            logger.info(f"Processed {result['processed_count']}/{result['total_count']} emails")
        else:
            logger.error(f"Batch processing failed: {result.get('error', 'Unknown error')}")
        
        # Process any pending LLM analyses
        analysis_result = processor.process_records_needing_analysis()
        if analysis_result['success'] and analysis_result['analyzed_count'] > 0:
            logger.info(f"Completed LLM analysis for {analysis_result['analyzed_count']} records")
        
        return result['success']
        
    except Exception as e:
        logger.error(f"Error in batch processing: {str(e)}")
        return False

def test_single_email(message_id: str):
    """
    Test processing a single email
    """
    try:
        from email_processor import MedicalEmailProcessor
        
        logger.info(f"Testing single email processing for message ID: {message_id}")
        
        processor = MedicalEmailProcessor()
        result = processor.process_single_email(message_id)
        
        if result['success']:
            logger.info("Single email processing completed successfully!")
            logger.info(f"Results: {result}")
        else:
            logger.error(f"Single email processing failed: {result.get('error', 'Unknown error')}")
        
        return result['success']
        
    except Exception as e:
        logger.error(f"Error testing single email: {str(e)}")
        return False

def validate_configuration():
    """
    Validate the system configuration
    """
    try:
        from config import Config
        
        logger.info("Validating configuration...")
        
        Config.validate()
        logger.info("✓ Configuration is valid!")
        
        # Test database connection
        try:
            from models import DatabaseManager
            db_manager = DatabaseManager()
            logger.info("✓ Database connection successful!")
        except Exception as e:
            logger.error(f"✗ Database connection failed: {str(e)}")
            return False
        
        # Test Gmail API
        try:
            from gmail_service import GmailService
            gmail_service = GmailService()
            logger.info("✓ Gmail API authentication successful!")
        except Exception as e:
            logger.error(f"✗ Gmail API authentication failed: {str(e)}")
            return False
        
        # Test LLM API
        try:
            from llm_analyzer import LLMAnalyzer
            llm_analyzer = LLMAnalyzer()
            logger.info("✓ LLM API configuration successful!")
        except Exception as e:
            logger.error(f"✗ LLM API configuration failed: {str(e)}")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Configuration validation failed: {str(e)}")
        return False

def create_env_file():
    """
    Create a template .env file
    """
    env_content = """# Gmail API Configuration
GMAIL_CLIENT_SECRET_FILE=client_secret.json.json
GMAIL_TOKEN_FILE=token.json

# MongoDB Configuration
MONGODB_URI=mongodb://localhost:27017/
MONGODB_DATABASE=medmaestro_gmail_agent

# Self-hosted LLM Configuration (Primary - configure this for your server)
USE_SELF_HOSTED_LLM=True
SELF_HOSTED_LLM_URL=http://192.168.1.100
SELF_HOSTED_LLM_PORT=8000

# LLM Configuration (Fallback options - configure at least one)
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Webhook Configuration for Gmail Push Notifications
WEBHOOK_URL=https://your-domain.com/webhook/gmail
WEBHOOK_SECRET=your_webhook_secret_here

# Flask Configuration
FLASK_PORT=5000
FLASK_DEBUG=True

# PDF Processing Configuration
PDF_STORAGE_PATH=pdfs/
MAX_PDF_SIZE_MB=50
"""
    
    with open('.env', 'w') as f:
        f.write(env_content)
    
    logger.info("Created .env template file. Please configure your settings.")

def main():
    parser = argparse.ArgumentParser(
        description='Medical Gmail Agent - Automated medical email processing system'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Webhook server command
    webhook_parser = subparsers.add_parser('webhook', help='Run webhook server for real-time processing')
    webhook_parser.add_argument('--setup-push', action='store_true', 
                               help='Setup Gmail push notifications before starting server')
    
    # Batch processing command
    batch_parser = subparsers.add_parser('batch', help='Run batch processing for recent emails')
    batch_parser.add_argument('--days', type=int, default=1, 
                             help='Number of days back to process (default: 1)')
    
    # Test command
    test_parser = subparsers.add_parser('test', help='Test processing a single email')
    test_parser.add_argument('message_id', help='Gmail message ID to test')
    
    # Setup commands
    setup_parser = subparsers.add_parser('setup', help='Setup and configuration commands')
    setup_group = setup_parser.add_mutually_exclusive_group(required=True)
    setup_group.add_argument('--validate', action='store_true', help='Validate configuration')
    setup_group.add_argument('--create-env', action='store_true', help='Create .env template file')
    setup_group.add_argument('--setup-push', action='store_true', help='Setup Gmail push notifications')
    
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)
    
    args = parser.parse_args()
    
    try:
        if args.command == 'webhook':
            if args.setup_push:
                logger.info("Setting up Gmail push notifications...")
                if not setup_gmail_push_notifications():
                    logger.error("Failed to setup push notifications. Continuing with webhook server...")
            
            run_webhook_server()
            
        elif args.command == 'batch':
            success = run_batch_processing(days_back=args.days)
            sys.exit(0 if success else 1)
            
        elif args.command == 'test':
            success = test_single_email(args.message_id)
            sys.exit(0 if success else 1)
            
        elif args.command == 'setup':
            if args.validate:
                success = validate_configuration()
                sys.exit(0 if success else 1)
            elif args.create_env:
                create_env_file()
            elif args.setup_push:
                success = setup_gmail_push_notifications()
                sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()