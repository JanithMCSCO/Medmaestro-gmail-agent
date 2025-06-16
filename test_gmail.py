#!/usr/bin/env python3
"""
Gmail Integration Test Script

This script tests Gmail API connectivity and basic email retrieval functionality
independently of the full medical email processing system.
"""

import sys
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_gmail_authentication():
    """Test Gmail API authentication"""
    try:
        from gmail_service import GmailService
        
        logger.info("🔐 Testing Gmail API authentication...")
        gmail_service = GmailService()
        
        if gmail_service.service:
            logger.info("✅ Gmail API authentication successful!")
            return True, gmail_service
        else:
            logger.error("❌ Gmail API authentication failed!")
            return False, None
            
    except Exception as e:
        logger.error(f"❌ Gmail authentication error: {str(e)}")
        return False, None

def test_email_listing(gmail_service, max_emails=5):
    """Test basic email listing"""
    try:
        logger.info(f"📧 Testing email listing (last {max_emails} emails)...")
        
        message_ids = gmail_service.get_recent_messages(max_results=max_emails)
        
        if message_ids:
            logger.info(f"✅ Found {len(message_ids)} recent emails")
            for i, msg_id in enumerate(message_ids, 1):
                logger.info(f"   Email {i}: {msg_id}")
            return True, message_ids
        else:
            logger.warning("⚠️  No emails found")
            return True, []
            
    except Exception as e:
        logger.error(f"❌ Email listing error: {str(e)}")
        return False, []

def test_email_details(gmail_service, message_id):
    """Test retrieving email details"""
    try:
        logger.info(f"📄 Testing email details retrieval for: {message_id}")
        
        # Get full message details
        message = gmail_service.get_message_details(message_id)
        if not message:
            logger.error("❌ Failed to get message details")
            return False, None
        
        # Extract basic info
        message_info = gmail_service.extract_message_info(message)
        
        logger.info("✅ Email details retrieved successfully:")
        logger.info(f"   Subject: {message_info['subject']}")
        logger.info(f"   Sender: {message_info['sender']}")
        logger.info(f"   Date: {message_info['date']}")
        
        return True, message_info
        
    except Exception as e:
        logger.error(f"❌ Email details error: {str(e)}")
        return False, None

def test_pdf_attachments(gmail_service, message_id):
    """Test PDF attachment extraction"""
    try:
        logger.info(f"📎 Testing PDF attachment extraction for: {message_id}")
        
        # Get message details first
        message = gmail_service.get_message_details(message_id)
        if not message:
            logger.error("❌ Failed to get message for attachment extraction")
            return False, []
        
        # Extract PDF attachments
        pdf_attachments = gmail_service.get_pdf_attachments(message)
        
        if pdf_attachments:
            logger.info(f"✅ Found {len(pdf_attachments)} PDF attachment(s):")
            for i, attachment in enumerate(pdf_attachments, 1):
                logger.info(f"   PDF {i}: {attachment['filename']} ({attachment['size']} bytes)")
            return True, pdf_attachments
        else:
            logger.info("ℹ️  No PDF attachments found in this email")
            return True, []
            
    except Exception as e:
        logger.error(f"❌ PDF attachment error: {str(e)}")
        return False, []

def test_medical_subject_parsing(gmail_service, message_ids):
    """Test medical subject parsing on real emails"""
    logger.info("🏥 Testing medical subject parsing...")
    
    medical_emails_found = 0
    
    for message_id in message_ids[:5]:  # Test first 5 emails
        try:
            message = gmail_service.get_message_details(message_id)
            if message:
                message_info = gmail_service.extract_message_info(message)
                subject = message_info['subject']
                
                # Try to parse medical info
                medical_info = gmail_service.parse_medical_subject(subject)
                
                if medical_info:
                    logger.info(f"✅ Medical email found!")
                    logger.info(f"   Subject: {subject}")
                    logger.info(f"   Request ID: {medical_info['request_id']}")
                    logger.info(f"   Patient: {medical_info['patient_name']}")
                    logger.info(f"   Test Type: {medical_info['test_type']}")
                    medical_emails_found += 1
                else:
                    logger.info(f"ℹ️  Non-medical email: {subject[:60]}...")
                    
        except Exception as e:
            logger.error(f"❌ Error parsing email {message_id}: {str(e)}")
    
    logger.info(f"📊 Found {medical_emails_found} medical emails out of {len(message_ids[:5])} tested")
    return medical_emails_found > 0

def test_medical_email_search(gmail_service):
    """Test searching for medical emails specifically"""
    try:
        logger.info("🔍 Testing medical email search...")
        
        medical_message_ids = gmail_service.search_medical_emails(days_back=7)
        
        if medical_message_ids:
            logger.info(f"✅ Found {len(medical_message_ids)} potential medical emails in last 7 days")
            return True, medical_message_ids
        else:
            logger.info("ℹ️  No medical emails found in last 7 days")
            return True, []
            
    except Exception as e:
        logger.error(f"❌ Medical email search error: {str(e)}")
        return False, []

def run_comprehensive_test():
    """Run all Gmail tests"""
    logger.info("🚀 Starting Gmail Integration Tests")
    logger.info("=" * 50)
    
    # Test 1: Authentication
    auth_success, gmail_service = test_gmail_authentication()
    if not auth_success:
        logger.error("💥 Authentication failed. Please check your Gmail API setup.")
        return False
    
    print()
    
    # Test 2: Email listing
    list_success, message_ids = test_email_listing(gmail_service, max_emails=10)
    if not list_success:
        logger.error("💥 Email listing failed.")
        return False
    
    if not message_ids:
        logger.warning("⚠️  No emails found. Your inbox might be empty.")
        return True
    
    print()
    
    # Test 3: Email details for first email
    details_success, message_info = test_email_details(gmail_service, message_ids[0])
    if not details_success:
        logger.error("💥 Email details retrieval failed.")
        return False
    
    print()
    
    # Test 4: PDF attachments for first few emails
    pdf_found = False
    for i, message_id in enumerate(message_ids[:3]):  # Check first 3 emails
        logger.info(f"Checking email {i+1} for PDF attachments...")
        pdf_success, pdf_attachments = test_pdf_attachments(gmail_service, message_id)
        if pdf_success and pdf_attachments:
            pdf_found = True
            break
    
    if not pdf_found:
        logger.warning("⚠️  No PDF attachments found in recent emails (this may be normal)")
    
    print()
    
    # Test 5: Medical subject parsing
    test_medical_subject_parsing(gmail_service, message_ids)
    
    print()
    
    # Test 6: Medical email search
    search_success, medical_emails = test_medical_email_search(gmail_service)
    
    print()
    logger.info("🎉 Gmail Integration Tests Completed Successfully!")
    logger.info("=" * 50)
    
    return True

def run_interactive_test():
    """Run interactive tests where user can specify what to test"""
    auth_success, gmail_service = test_gmail_authentication()
    if not auth_success:
        return False
    
    while True:
        print("\n" + "=" * 50)
        print("Gmail Integration Test Menu:")
        print("1. List recent emails")
        print("2. Get email details by ID")
        print("3. Check PDF attachments by email ID")
        print("4. Search for medical emails")
        print("5. Test medical subject parsing")
        print("6. Run all tests")
        print("0. Exit")
        print("=" * 50)
        
        choice = input("Enter your choice (0-6): ").strip()
        
        if choice == "0":
            break
        elif choice == "1":
            test_email_listing(gmail_service)
        elif choice == "2":
            message_id = input("Enter Gmail message ID: ").strip()
            test_email_details(gmail_service, message_id)
        elif choice == "3":
            message_id = input("Enter Gmail message ID: ").strip()
            test_pdf_attachments(gmail_service, message_id)
        elif choice == "4":
            days = input("Enter days back to search (default 7): ").strip()
            days = int(days) if days.isdigit() else 7
            gmail_service.search_medical_emails(days_back=days)
        elif choice == "5":
            _, message_ids = test_email_listing(gmail_service, max_emails=5)
            if message_ids:
                test_medical_subject_parsing(gmail_service, message_ids)
        elif choice == "6":
            run_comprehensive_test()
        else:
            print("Invalid choice. Please try again.")

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        run_interactive_test()
    else:
        run_comprehensive_test()

if __name__ == "__main__":
    main() 