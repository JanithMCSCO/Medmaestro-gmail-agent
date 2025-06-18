#!/usr/bin/env python3
"""
Gmail to MongoDB Medical Records Processor

Processes medical emails from Gmail and stores in MongoDB with:
- Request ID, Patient name, Test type
- PDF file storage
- Clinical interpretation text (everything after "Clinical Interpretation")
"""

import os
import re
import logging
import requests
from datetime import datetime
from typing import Dict, Optional, List

from gmail_service import GmailService
from pdf_extractor import PDFTextExtractor
from models import DatabaseManager, MedicalRecord, EmailHistory

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ClinicalTextProcessor:
    """Process extracted text to get clinical interpretation"""
    
    @staticmethod
    def extract_clinical_interpretation(text: str) -> Dict[str, str]:
        """
        Extract text after "Clinical Interpretation" and create test summary
        """
        if not text:
            return {
                'clinical_interpretation': '',
                'test_summary': '',
                'full_text': text
            }
        
        # Look for "Clinical Interpretation" (case insensitive)
        pattern = r'clinical\s+interpretation[:\s]*'
        match = re.search(pattern, text, re.IGNORECASE)
        
        if match:
            # Extract everything after "Clinical Interpretation"
            start_pos = match.end()
            clinical_interpretation = text[start_pos:].strip()
            
            # Use the full clinical interpretation as test summary
            test_summary = clinical_interpretation.strip()
            
            logger.info(f"✅ Found Clinical Interpretation section ({len(clinical_interpretation)} characters)")
            
            return {
                'clinical_interpretation': clinical_interpretation,
                'test_summary': test_summary,
                'full_text': text
            }
        else:
            # No "Clinical Interpretation" found, use full text
            logger.warning("⚠️ No 'Clinical Interpretation' section found, using full text")
            
            # Use the full text as test summary (fallback case)
            test_summary = text.strip()
            
            return {
                'clinical_interpretation': text,
                'test_summary': test_summary,
                'full_text': text
            }

class GmailToMongoProcessor:
    """Main processor for Gmail to MongoDB medical records"""
    
    def __init__(self):
        self.gmail_service = GmailService()
        self.pdf_extractor = PDFTextExtractor()
        self.db_manager = DatabaseManager()
        self.medical_record = MedicalRecord(self.db_manager)
        self.email_history = EmailHistory(self.db_manager)
        self.text_processor = ClinicalTextProcessor()
    
    def process_recent_emails(self, max_emails: int = 20) -> Dict[str, int]:
        """Process recent emails and store in MongoDB"""
        
        logger.info("🚀 Starting Gmail to MongoDB Processing")
        logger.info("=" * 50)
        
        # Initialize counters
        stats = {
            'emails_checked': 0,
            'medical_emails_found': 0,
            'records_created': 0,
            'records_updated': 0,
            'pdfs_processed': 0,
            'errors': 0
        }
        
        try:
            # Get recent messages
            logger.info(f"📧 Fetching last {max_emails} emails...")
            message_ids = self.gmail_service.get_recent_messages(max_results=max_emails)
            
            if not message_ids:
                logger.warning("⚠️ No emails found")
                return stats
            
            logger.info(f"✅ Found {len(message_ids)} emails to process")
            stats['emails_checked'] = len(message_ids)
            
            # Process each email
            for i, message_id in enumerate(message_ids, 1):
                try:
                    logger.info(f"\n📨 Processing email {i}/{len(message_ids)} (ID: {message_id})")
                    
                    # Check if already processed
                    if self.email_history.is_email_processed(message_id):
                        logger.info("⏭️ Email already processed, skipping...")
                        continue
                    
                    # Get message details
                    message = self.gmail_service.get_message_details(message_id)
                    if not message:
                        logger.warning(f"⚠️ Could not get details for message {message_id}")
                        continue
                    
                    # Extract message info
                    message_info = self.gmail_service.extract_message_info(message)
                    subject = message_info['subject']
                    sender = message_info['sender']
                    
                    logger.info(f"   Subject: {subject}")
                    logger.info(f"   From: {sender}")
                    
                    # Parse medical information from subject
                    medical_info = self.gmail_service.parse_medical_subject(subject)
                    
                    if not medical_info:
                        logger.info("   ℹ️ Not a medical email, skipping...")
                        # Record as processed (non-medical)
                        self.email_history.add_processed_email(
                            message_id, subject, sender, 
                            "", "", "", False, None, "non_medical"
                        )
                        continue
                    
                    # Extract medical details
                    request_id = medical_info['request_id']
                    patient_name = medical_info['patient_name']
                    test_type = medical_info['test_type']
                    
                    logger.info(f"   🏥 Medical Email Detected:")
                    logger.info(f"      Request ID: {request_id}")
                    logger.info(f"      Patient: {patient_name}")
                    logger.info(f"      Test Type: {test_type}")
                    
                    stats['medical_emails_found'] += 1
                    
                    # Get PDF attachments
                    pdf_attachments = self.gmail_service.get_pdf_attachments(message)
                    
                    if not pdf_attachments:
                        logger.info("   📎 No PDF attachments found")
                        # Record as processed (no PDF)
                        self.email_history.add_processed_email(
                            message_id, subject, sender,
                            request_id, patient_name, test_type, False
                        )
                        continue
                    
                    logger.info(f"   📎 Found {len(pdf_attachments)} PDF attachment(s)")
                    
                    # Process each PDF
                    for j, attachment in enumerate(pdf_attachments, 1):
                        try:
                            result = self.process_pdf_attachment(
                                attachment, request_id, patient_name, test_type, message_id
                            )
                            
                            if result['success']:
                                stats['pdfs_processed'] += 1
                                if result['action'] == 'created':
                                    stats['records_created'] += 1
                                else:
                                    stats['records_updated'] += 1
                                
                                logger.info(f"      ✅ PDF {j} processed successfully ({result['action']})")
                                
                                # Record as processed (success)
                                self.email_history.add_processed_email(
                                    message_id, subject, sender,
                                    request_id, patient_name, test_type, True,
                                    attachment['filename'], "success"
                                )
                            else:
                                logger.error(f"      ❌ Failed to process PDF {j}: {result['error']}")
                                stats['errors'] += 1
                                
                                # Record as processed (error)
                                self.email_history.add_processed_email(
                                    message_id, subject, sender,
                                    request_id, patient_name, test_type, True,
                                    attachment['filename'], "error", result['error']
                                )
                        
                        except Exception as e:
                            logger.error(f"      ❌ Error processing PDF {j}: {str(e)}")
                            stats['errors'] += 1
                            continue
                
                except Exception as e:
                    logger.error(f"❌ Error processing email {message_id}: {str(e)}")
                    stats['errors'] += 1
                    continue
            
            # Print summary
            self.print_processing_summary(stats)
            return stats
            
        except Exception as e:
            logger.error(f"❌ Gmail processing failed: {str(e)}")
            import traceback
            logger.error(f"📋 Full error: {traceback.format_exc()}")
            stats['errors'] += 1
            return stats
    
    def process_pdf_attachment(
        self, 
        attachment: Dict, 
        request_id: str, 
        patient_name: str, 
        test_type: str, 
        message_id: str
    ) -> Dict:
        """Process a single PDF attachment"""
        
        pdf_filename = attachment['filename']
        pdf_data = attachment['data']
        
        try:
            logger.info(f"         🔤 Extracting text from {pdf_filename}...")
            
            # Extract text from PDF
            extraction_result = self.pdf_extractor.extract_text(pdf_data, pdf_filename)
            
            if not extraction_result.get('success'):
                return {
                    'success': False,
                    'error': f"Text extraction failed: {extraction_result.get('error', 'Unknown error')}"
                }
            
            full_text = extraction_result['text']
            logger.info(f"         ✅ Extracted {len(full_text)} characters using {extraction_result['extraction_method']}")
            
            # Process clinical interpretation
            processed_text = self.text_processor.extract_clinical_interpretation(full_text)
            clinical_interpretation = processed_text['clinical_interpretation']
            test_summary = processed_text['test_summary']
            
            logger.info(f"         📋 Clinical interpretation: {len(clinical_interpretation)} characters")
            logger.info(f"         📝 Test summary: {len(test_summary)} characters extracted")
            
            # Store in MongoDB
            logger.info(f"         💾 Storing in MongoDB...")
            mongo_result = self.medical_record.create_or_update(
                request_id=request_id,
                patient_name=patient_name,
                test_type=test_type,
                pdf_content=pdf_data,
                extracted_text=clinical_interpretation,  # Store only clinical interpretation
                email_message_id=message_id,
                original_filename=pdf_filename,
                test_summary=test_summary
            )
            
            # Update the record with test summary manually
            if mongo_result.get('record_id'):
                from bson import ObjectId
                self.medical_record.collection.update_one(
                    {"_id": ObjectId(mongo_result['record_id'])},
                    {"$set": {"test_summary": test_summary}}
                )
            
            logger.info(f"         ✅ MongoDB: Record {mongo_result['action']} (ID: {mongo_result['record_id']})")
            
            # Handle duplicate case - check if we should prepare LLM prompt
            if mongo_result['is_duplicate']:
                logger.info(f"         🔄 Duplicate detected - collated text length: {len(mongo_result['collated_text'])}")
                
                # Check if we have both Blood Work and CT Scan
                self.handle_duplicate_record(mongo_result['record_id'], request_id, patient_name)
            
            return {
                'success': True,
                'action': mongo_result['action'],
                'record_id': mongo_result['record_id'],
                'is_duplicate': mongo_result['is_duplicate']
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def handle_duplicate_record(self, record_id: str, request_id: str, patient_name: str):
        """Handle duplicate records - check if we have both Blood Work and CT Scan"""
        try:
            from bson import ObjectId
            
            # Get the updated record from MongoDB
            record = self.medical_record.collection.find_one({"_id": ObjectId(record_id)})
            
            if not record:
                logger.error(f"         ❌ Could not find record {record_id}")
                return
            
            # Extract individual test records from PDF files
            test_records = []
            
            for pdf_file in record.get('pdf_files', []):
                # Get test type and summary from the PDF file record
                pdf_test_type = pdf_file.get('test_type', '')
                pdf_test_summary = pdf_file.get('test_summary', '')
                filename = pdf_file.get('filename', '')
                
                # Determine the standardized test type
                standardized_test_type = self.determine_test_type(filename, pdf_test_type)
                
                test_records.append({
                    'test_type': standardized_test_type,
                    'test_summary': pdf_test_summary,
                    'filename': filename
                })
            
            logger.info(f"         🧪 Found {len(test_records)} test records:")
            for i, record_info in enumerate(test_records, 1):
                logger.info(f"            {i}. {record_info['test_type']} - {len(record_info['test_summary'])} characters")
            
            # Check if we have both Blood Work and CT Scan
            blood_records = [r for r in test_records if r['test_type'] == 'Blood Work']
            ct_records = [r for r in test_records if r['test_type'] == 'CT Scan']
            
            if blood_records and ct_records:
                logger.info(f"         🎯 Both Blood Work and CT Scan detected - preparing LLM prompt!")
                
                # Use the first record of each type (in case there are multiple)
                blood_summary = blood_records[0]['test_summary']
                ct_summary = ct_records[0]['test_summary']
                
                # Generate and print the LLM prompt
                self.generate_and_print_llm_prompt(
                    request_id, patient_name, 'Blood Work', blood_summary, 'CT Scan', ct_summary
                )
            else:
                logger.info(f"         ℹ️ Missing required test types - no LLM analysis needed")
                logger.info(f"            Blood Work records: {len(blood_records)}")
                logger.info(f"            CT Scan records: {len(ct_records)}")
                
        except Exception as e:
            logger.error(f"         ❌ Error handling duplicate record: {str(e)}")

    def determine_test_type(self, filename: str, test_type: str) -> str:
        """Determine standardized test type from filename and test_type"""
        
        # Check filename first
        filename_lower = filename.lower()
        if 'blood' in filename_lower or 'lab' in filename_lower or 'hematology' in filename_lower:
            return 'Blood Work'
        elif 'ct' in filename_lower or 'scan' in filename_lower or 'radiology' in filename_lower:
            return 'CT Scan'
        
        # Check test_type field
        test_type_lower = test_type.lower()
        if 'blood' in test_type_lower:
            return 'Blood Work'
        elif 'ct' in test_type_lower:
            return 'CT Scan'
        
        return 'Unknown'

    def generate_and_print_llm_prompt(
        self, 
        request_id: str, 
        patient_name: str, 
        test_type_1: str,
        test_summary_1: str, 
        test_type_2: str,
        test_summary_2: str
    ):
        """Generate and print the LLM prompt for review, then call LLM API"""
        
        logger.info(f"\n" + "=" * 70)
        logger.info(f"🤖 LLM PROMPT GENERATED FOR REVIEW")
        logger.info(f"=" * 70)
        logger.info(f"Request ID: {request_id}")
        logger.info(f"Patient: {patient_name}")
        logger.info(f"=" * 70)
        
        # Build the user content in the new format you requested
        user_content = f"Record 1 - {test_type_1} - {test_summary_1}\n\nRecord 2 - {test_type_2} - {test_summary_2}"
        
        # Build the complete prompt structure
        prompt_structure = {
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful medical assistant to a medical professional. Provide detailed responses to the questions that are asked of you. The upcoming text is a combination of results from a Blood test report and a CT scan. I want you to use your deep medical knowledge to help diagnose the patient's condition based on the information in the reports"
                },
                {
                    "role": "user",
                    "content": user_content
                }
            ],
            "max_tokens": 1000,
            "temperature": 0.7,
            "top_p": 0.9,
            "repetition_penalty": 1.1
        }
        
        # Print the prompt structure for review
        print("\n🔍 SYSTEM PROMPT:")
        print(f"   {prompt_structure['messages'][0]['content']}")
        
        print("\n🔍 USER PROMPT:")
        print(f"   {prompt_structure['messages'][1]['content']}")
        
        # Get the actual server URL from config
        from config import Config
        server_url = f"{Config.SELF_HOSTED_LLM_URL}:{Config.SELF_HOSTED_LLM_PORT}"
        
        print("\n🔍 FULL CURL COMMAND:")
        print(f"curl -X POST \"{server_url}/v1/chat/completions\" \\")
        print(f"  -H \"Content-Type: application/json\" \\")
        print(f"  -H \"Accept: application/json\" \\")
        print(f"  -d '{{\n    \"messages\": [")
        print(f"      {{")
        print(f"        \"role\": \"system\",")
        print(f"        \"content\": \"{prompt_structure['messages'][0]['content']}\"")
        print(f"      }},")
        print(f"      {{")
        print(f"        \"role\": \"user\",")
        print(f"        \"content\": \"{prompt_structure['messages'][1]['content']}\"")
        print(f"      }}")
        print(f"    ],")
        print(f"    \"max_tokens\": 1000,")
        print(f"    \"temperature\": 0.7,")
        print(f"    \"top_p\": 0.9,")
        print(f"    \"repetition_penalty\": 1.1")
        print(f"  }}'")
        
        logger.info(f"=" * 70)
        logger.info(f"📝 PROMPT READY FOR REVIEW - Check the output above!")
        logger.info(f"=" * 70)
        
        # Now make the actual LLM API call
        self.call_llm_api(prompt_structure, server_url, request_id, patient_name)

    def call_llm_api(self, prompt_structure: dict, server_url: str, request_id: str, patient_name: str):
        """Make the actual LLM API call and display response"""
        
        try:
            logger.info(f"\n🚀 CALLING LLM API...")
            logger.info(f"   Server: {server_url}")
            
            # Make the API call
            response = requests.post(
                f"{server_url}/v1/chat/completions",
                json=prompt_structure,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                timeout=60
            )
            
            if response.status_code == 200:
                response_data = response.json()
                
                # Extract the LLM response
                if 'choices' in response_data and len(response_data['choices']) > 0:
                    llm_response = response_data['choices'][0]['message']['content'].strip()
                    
                    logger.info(f"\n" + "=" * 70)
                    logger.info(f"🎯 LLM RESPONSE")
                    logger.info(f"=" * 70)
                    logger.info(f"Request ID: {request_id}")
                    logger.info(f"Patient: {patient_name}")
                    logger.info(f"=" * 70)
                    
                    print(f"\n🤖 LLM ANALYSIS:")
                    print(f"{llm_response}")
                    
                    logger.info(f"=" * 70)
                    logger.info(f"✅ LLM analysis completed successfully!")
                    logger.info(f"=" * 70)
                    
                else:
                    logger.error(f"❌ Unexpected response format: {response_data}")
                    
            else:
                logger.error(f"❌ LLM API call failed: HTTP {response.status_code}")
                logger.error(f"   Response: {response.text}")
                
        except requests.exceptions.Timeout:
            logger.error(f"❌ LLM API call timed out after 60 seconds")
            
        except requests.exceptions.ConnectionError:
            logger.error(f"❌ Could not connect to LLM server at {server_url}")
            logger.error(f"   Make sure your LLM server is running and accessible")
            
        except Exception as e:
            logger.error(f"❌ LLM API call failed: {str(e)}")

    def print_processing_summary(self, stats: Dict[str, int]):
        """Print processing summary"""
        
        logger.info("\n" + "=" * 50)
        logger.info("📊 PROCESSING SUMMARY")
        logger.info("=" * 50)
        logger.info(f"📧 Total emails checked: {stats['emails_checked']}")
        logger.info(f"🏥 Medical emails found: {stats['medical_emails_found']}")
        logger.info(f"📄 PDFs processed: {stats['pdfs_processed']}")
        logger.info(f"✅ Records created: {stats['records_created']}")
        logger.info(f"🔄 Records updated: {stats['records_updated']}")
        logger.info(f"❌ Errors: {stats['errors']}")
        
        if stats['medical_emails_found'] > 0:
            logger.info(f"\n💡 Next steps:")
            logger.info(f"   1. Check MongoDB for stored records")
            logger.info(f"   2. Review clinical interpretations")
            logger.info(f"   3. Run LLM analysis on duplicates if any")

def main():
    """Main entry point"""
    import sys
    
    # Get number of emails to process
    max_emails = 2
    if len(sys.argv) > 1:
        try:
            max_emails = int(sys.argv[1])
        except ValueError:
            logger.warning("Invalid number provided, using default (2)")
    
    # Initialize processor
    processor = GmailToMongoProcessor()
    
    # Process emails
    stats = processor.process_recent_emails(max_emails)
    
    logger.info("\n🏁 Gmail to MongoDB processing completed!")

if __name__ == '__main__':
    main() 