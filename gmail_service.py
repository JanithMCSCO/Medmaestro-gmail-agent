import os
import base64
import email
import re
from typing import Dict, List, Optional, Tuple
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import logging
from config import Config

logger = logging.getLogger(__name__)

class GmailService:
    def __init__(self):
        self.service = None
        self.authenticate()
    
    def authenticate(self):
        """Authenticate with Gmail API"""
        creds = None
        
        # Load existing token
        if os.path.exists(Config.GMAIL_TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(Config.GMAIL_TOKEN_FILE, Config.GMAIL_SCOPES)
        
        # If no valid credentials available, let user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    Config.GMAIL_CLIENT_SECRET_FILE, Config.GMAIL_SCOPES)
                
                # Check if we're in a headless environment
                import os
                if os.getenv('DISPLAY') is None or os.getenv('SSH_CONNECTION') is not None:
                    # Headless/SSH environment - use console flow
                    logger.info("Detected headless environment, using console authentication flow...")
                    creds = flow.run_console()
                else:
                    # GUI environment - use local server
                    creds = flow.run_local_server(port=0)
            
            # Save credentials for next run
            with open(Config.GMAIL_TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())
        
        self.service = build('gmail', 'v1', credentials=creds)
        logger.info("Gmail API authenticated successfully")
    
    def parse_medical_subject(self, subject: str) -> Optional[Dict[str, str]]:
        """
        Parse medical email subject to extract Request ID, test type, and patient name
        Expected format examples:
        - "Request ID: REQ123 | Test: Blood Work | Patient: John Doe"
        - "REQ456 - MRI Scan - Jane Smith"
        - "Request REQ789 Blood Test for Patient Mary Johnson"
        """
        
        # Pattern 1: Request ID: XXX | Test: YYY | Patient: ZZZ
        pattern1 = r'Request\s+ID:\s*([A-Z0-9]+).*?Test:\s*([^|]+).*?Patient:\s*([^|]+)'
        match = re.search(pattern1, subject, re.IGNORECASE)
        if match:
            return {
                'request_id': match.group(1).strip(),
                'test_type': match.group(2).strip(),
                'patient_name': match.group(3).strip()
            }
        
        # Pattern 2: REQXXX - Test Type - Patient Name
        pattern2 = r'(REQ[A-Z0-9]+)\s*-\s*([^-]+)\s*-\s*(.+)'
        match = re.search(pattern2, subject, re.IGNORECASE)
        if match:
            return {
                'request_id': match.group(1).strip(),
                'test_type': match.group(2).strip(),
                'patient_name': match.group(3).strip()
            }
        
        # Pattern 3: Request REQXXX Test Type for Patient Name
        pattern3 = r'Request\s+(REQ[A-Z0-9]+)\s+(.+?)\s+for\s+Patient\s+(.+)'
        match = re.search(pattern3, subject, re.IGNORECASE)
        if match:
            return {
                'request_id': match.group(1).strip(),
                'test_type': match.group(2).strip(),
                'patient_name': match.group(3).strip()
            }
        
        # Pattern 4: More flexible pattern
        # Look for REQ followed by alphanumeric
        req_match = re.search(r'REQ[A-Z0-9]+', subject, re.IGNORECASE)
        if req_match:
            request_id = req_match.group()
            
            # Try to extract patient name (usually appears after "Patient" or at the end)
            patient_match = re.search(r'Patient[:\s]+([A-Za-z\s]+)', subject, re.IGNORECASE)
            if not patient_match:
                # Try to get name from the end of subject
                words = subject.split()
                if len(words) >= 3:
                    patient_name = ' '.join(words[-2:])  # Take last two words as name
                else:
                    patient_name = "Unknown Patient"
            else:
                patient_name = patient_match.group(1).strip()
            
            # Extract test type (everything between request ID and patient name)
            test_start = subject.find(request_id) + len(request_id)
            if patient_match:
                test_end = patient_match.start()
                test_type = subject[test_start:test_end].strip(' -|')
            else:
                # Take middle portion as test type
                words = subject.split()
                req_index = next((i for i, word in enumerate(words) if 'REQ' in word.upper()), 0)
                if len(words) > req_index + 1:
                    test_type = ' '.join(words[req_index+1:-2])
                else:
                    test_type = "Unknown Test"
            
            if test_type:
                return {
                    'request_id': request_id,
                    'test_type': test_type,
                    'patient_name': patient_name
                }
        
        logger.warning(f"Could not parse medical subject: {subject}")
        return None
    
    def get_message_details(self, message_id: str) -> Optional[Dict]:
        """Get full message details including attachments"""
        try:
            message = self.service.users().messages().get(
                userId='me', 
                id=message_id,
                format='full'
            ).execute()
            
            return message
        except HttpError as error:
            logger.error(f"Error getting message {message_id}: {error}")
            return None
    
    def extract_message_info(self, message: Dict) -> Dict:
        """Extract key information from Gmail message"""
        headers = message['payload'].get('headers', [])
        
        # Extract headers
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), '')
        date = next((h['value'] for h in headers if h['name'] == 'Date'), '')
        
        return {
            'id': message['id'],
            'subject': subject,
            'sender': sender,
            'date': date,
            'payload': message['payload']
        }
    
    def get_pdf_attachments(self, message: Dict) -> List[Dict]:
        """Extract PDF attachments from Gmail message"""
        attachments = []
        
        def process_part(part):
            if part.get('filename') and part.get('filename').lower().endswith('.pdf'):
                attachment_id = part['body'].get('attachmentId')
                if attachment_id:
                    try:
                        attachment = self.service.users().messages().attachments().get(
                            userId='me',
                            messageId=message['id'],
                            id=attachment_id
                        ).execute()
                        
                        data = base64.urlsafe_b64decode(attachment['data'])
                        attachments.append({
                            'filename': part['filename'],
                            'data': data,
                            'size': len(data)
                        })
                        logger.info(f"Extracted PDF: {part['filename']} ({len(data)} bytes)")
                    except HttpError as error:
                        logger.error(f"Error downloading attachment: {error}")
            
            # Recursively process multipart messages
            if 'parts' in part:
                for subpart in part['parts']:
                    process_part(subpart)
        
        # Process message payload
        if 'parts' in message['payload']:
            for part in message['payload']['parts']:
                process_part(part)
        else:
            process_part(message['payload'])
        
        return attachments
    
    def get_recent_messages(self, query: str = '', max_results: int = 10) -> List[str]:
        """Get recent message IDs, optionally filtered by query"""
        try:
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            return [msg['id'] for msg in messages]
        
        except HttpError as error:
            logger.error(f"Error getting messages: {error}")
            return []
    
    def setup_push_notifications(self, webhook_url: str, topic_name: str = 'gmail-push') -> bool:
        """
        Setup Gmail Push notifications
        Note: This requires additional setup in Google Cloud Console
        """
        try:
            request = {
                'labelIds': ['INBOX'],
                'topicName': f'projects/{self.get_project_id()}/topics/{topic_name}'
            }
            
            self.service.users().watch(userId='me', body=request).execute()
            logger.info(f"Push notifications setup for topic: {topic_name}")
            return True
            
        except HttpError as error:
            logger.error(f"Error setting up push notifications: {error}")
            return False
    
    def get_project_id(self) -> str:
        """Extract project ID from credentials"""
        # This would need to be configured based on your Google Cloud project
        # For now, return a placeholder
        return "your-google-cloud-project-id"
    
    def mark_as_read(self, message_id: str) -> bool:
        """Mark message as read"""
        try:
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
            return True
        except HttpError as error:
            logger.error(f"Error marking message as read: {error}")
            return False
    
    def search_medical_emails(self, days_back: int = 7) -> List[str]:
        """Search for emails that might contain medical data"""
        # Search query to find emails with common medical keywords and PDF attachments
        query = f'has:attachment filename:pdf (REQ OR "Request ID" OR "Patient" OR "Test" OR "Medical") newer_than:{days_back}d'
        
        return self.get_recent_messages(query=query, max_results=50) 