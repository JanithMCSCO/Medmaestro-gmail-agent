import logging
from typing import Dict, List, Optional
from datetime import datetime
from gmail_service import GmailService
from pdf_extractor import PDFTextExtractor
from llm_analyzer import LLMAnalyzer
from models import DatabaseManager, MedicalRecord, EmailHistory

logger = logging.getLogger(__name__)

class MedicalEmailProcessor:
    """
    Main orchestrator for processing medical emails
    """
    
    def __init__(self):
        self.gmail_service = GmailService()
        self.pdf_extractor = PDFTextExtractor()
        self.llm_analyzer = LLMAnalyzer()
        self.db_manager = DatabaseManager()
        self.medical_records = MedicalRecord(self.db_manager)
        self.email_history = EmailHistory(self.db_manager)
        
        logger.info("Medical Email Processor initialized")
    
    def process_single_email(self, message_id: str) -> Dict:
        """
        Process a single email message
        """
        try:
            # Get message details
            message = self.gmail_service.get_message_details(message_id)
            if not message:
                return {'success': False, 'error': 'Failed to get message details'}
            
            # Extract message info
            message_info = self.gmail_service.extract_message_info(message)
            
            # Check if already processed
            if self.email_history.is_email_processed(message_id):
                logger.info(f"Email {message_id} already processed, skipping")
                return {'success': True, 'action': 'skipped', 'reason': 'already_processed'}
            
            # Parse medical information from subject
            medical_info = self.gmail_service.parse_medical_subject(message_info['subject'])
            if not medical_info:
                logger.warning(f"Could not parse medical info from subject: {message_info['subject']}")
                self.email_history.add_processed_email(
                    message_id=message_id,
                    subject=message_info['subject'],
                    sender=message_info['sender'],
                    request_id="",
                    patient_name="",
                    test_type="",
                    has_pdf=False,
                    processing_status="failed",
                    error_message="Could not parse medical information from subject"
                )
                return {'success': False, 'error': 'Could not parse medical information from subject'}
            
            # Extract PDF attachments
            pdf_attachments = self.gmail_service.get_pdf_attachments(message)
            if not pdf_attachments:
                logger.warning(f"No PDF attachments found in email {message_id}")
                self.email_history.add_processed_email(
                    message_id=message_id,
                    subject=message_info['subject'],
                    sender=message_info['sender'],
                    request_id=medical_info['request_id'],
                    patient_name=medical_info['patient_name'],
                    test_type=medical_info['test_type'],
                    has_pdf=False,
                    processing_status="failed",
                    error_message="No PDF attachments found"
                )
                return {'success': False, 'error': 'No PDF attachments found'}
            
            # Process each PDF attachment
            results = []
            for pdf_attachment in pdf_attachments:
                try:
                    result = self._process_pdf_attachment(
                        pdf_attachment, 
                        medical_info, 
                        message_id,
                        message_info
                    )
                    results.append(result)
                except Exception as e:
                    logger.error(f"Error processing PDF {pdf_attachment['filename']}: {str(e)}")
                    results.append({
                        'success': False, 
                        'error': str(e), 
                        'filename': pdf_attachment['filename']
                    })
            
            # Mark email as read
            self.gmail_service.mark_as_read(message_id)
            
            return {
                'success': True,
                'message_id': message_id,
                'medical_info': medical_info,
                'pdf_results': results,
                'processed_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error processing email {message_id}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _process_pdf_attachment(
        self, 
        pdf_attachment: Dict, 
        medical_info: Dict, 
        message_id: str,
        message_info: Dict
    ) -> Dict:
        """
        Process a single PDF attachment
        """
        
        # Extract text from PDF
        pdf_result = self.pdf_extractor.extract_text(
            pdf_attachment['data'], 
            pdf_attachment['filename']
        )
        
        if not pdf_result['success']:
            logger.error(f"Failed to extract text from {pdf_attachment['filename']}: {pdf_result['error']}")
            self.email_history.add_processed_email(
                message_id=message_id,
                subject=message_info['subject'],
                sender=message_info['sender'],
                request_id=medical_info['request_id'],
                patient_name=medical_info['patient_name'],
                test_type=medical_info['test_type'],
                has_pdf=True,
                pdf_filename=pdf_attachment['filename'],
                processing_status="failed",
                error_message=f"PDF text extraction failed: {pdf_result['error']}"
            )
            return pdf_result
        
        extracted_text = pdf_result['text']
        
        # Validate that it contains medical content
        validation = self.pdf_extractor.validate_medical_content(extracted_text)
        if not validation['is_likely_medical']:
            logger.warning(f"PDF {pdf_attachment['filename']} may not contain medical content")
        
        # Store in database
        try:
            db_result = self.medical_records.create_or_update(
                request_id=medical_info['request_id'],
                patient_name=medical_info['patient_name'],
                test_type=medical_info['test_type'],
                pdf_content=pdf_attachment['data'],
                extracted_text=extracted_text,
                email_message_id=message_id,
                original_filename=pdf_attachment['filename']
            )
            
            # Record successful email processing
            self.email_history.add_processed_email(
                message_id=message_id,
                subject=message_info['subject'],
                sender=message_info['sender'],
                request_id=medical_info['request_id'],
                patient_name=medical_info['patient_name'],
                test_type=medical_info['test_type'],
                has_pdf=True,
                pdf_filename=pdf_attachment['filename'],
                processing_status="success"
            )
            
            # If this is a duplicate (collated document), trigger LLM analysis
            if db_result['is_duplicate']:
                logger.info(f"Duplicate record detected for {medical_info['patient_name']} - {medical_info['request_id']}")
                analysis_result = self._analyze_collated_documents(
                    db_result['collated_text'],
                    medical_info,
                    db_result['record_id']
                )
                db_result['llm_analysis'] = analysis_result
            
            return {
                'success': True,
                'filename': pdf_attachment['filename'],
                'database_result': db_result,
                'text_length': len(extracted_text),
                'medical_validation': validation
            }
            
        except Exception as e:
            logger.error(f"Error storing PDF data: {str(e)}")
            self.email_history.add_processed_email(
                message_id=message_id,
                subject=message_info['subject'],
                sender=message_info['sender'],
                request_id=medical_info['request_id'],
                patient_name=medical_info['patient_name'],
                test_type=medical_info['test_type'],
                has_pdf=True,
                pdf_filename=pdf_attachment['filename'],
                processing_status="failed",
                error_message=f"Database storage failed: {str(e)}"
            )
            return {'success': False, 'error': str(e)}
    
    def _analyze_collated_documents(
        self, 
        collated_text: str, 
        medical_info: Dict, 
        record_id: str
    ) -> Dict:
        """
        Analyze collated documents using LLM
        """
        try:
            analysis_result = self.llm_analyzer.analyze_medical_documents(
                collated_text=collated_text,
                patient_name=medical_info['patient_name'],
                request_id=medical_info['request_id'],
                test_type=medical_info['test_type']
            )
            
            if analysis_result['success']:
                # Store analysis result in database
                self.medical_records.mark_analysis_complete(
                    record_id=record_id,
                    analysis_result=analysis_result['analysis']
                )
                
                logger.info(f"LLM analysis completed for record {record_id}")
                
                # Here you could add additional actions like:
                # - Send email with analysis results
                # - Create alerts for critical findings
                # - Generate reports
                
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error in LLM analysis: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'analysis': ''
            }
    
    def process_recent_emails(self, days_back: int = 1) -> Dict:
        """
        Process recent medical emails
        """
        try:
            # Search for medical emails
            message_ids = self.gmail_service.search_medical_emails(days_back=days_back)
            
            if not message_ids:
                logger.info(f"No medical emails found in the last {days_back} days")
                return {'success': True, 'processed_count': 0, 'results': []}
            
            logger.info(f"Found {len(message_ids)} potential medical emails to process")
            
            results = []
            successful_count = 0
            
            for message_id in message_ids:
                try:
                    result = self.process_single_email(message_id)
                    results.append(result)
                    if result['success']:
                        successful_count += 1
                except Exception as e:
                    logger.error(f"Error processing message {message_id}: {str(e)}")
                    results.append({
                        'success': False, 
                        'message_id': message_id, 
                        'error': str(e)
                    })
            
            logger.info(f"Processed {successful_count}/{len(message_ids)} emails successfully")
            
            return {
                'success': True,
                'processed_count': successful_count,
                'total_count': len(message_ids),
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Error processing recent emails: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def process_records_needing_analysis(self) -> Dict:
        """
        Process any existing records that need LLM analysis
        """
        try:
            records = self.medical_records.get_records_needing_analysis()
            
            if not records:
                logger.info("No records need LLM analysis")
                return {'success': True, 'analyzed_count': 0}
            
            logger.info(f"Found {len(records)} records needing LLM analysis")
            
            analyzed_count = 0
            for record in records:
                try:
                    medical_info = {
                        'patient_name': record['patient_name'],
                        'request_id': record['request_id'],
                        'test_type': record['test_type']
                    }
                    
                    analysis_result = self._analyze_collated_documents(
                        record['extracted_text'],
                        medical_info,
                        str(record['_id'])
                    )
                    
                    if analysis_result['success']:
                        analyzed_count += 1
                        
                except Exception as e:
                    logger.error(f"Error analyzing record {record['_id']}: {str(e)}")
                    continue
            
            logger.info(f"Analyzed {analyzed_count}/{len(records)} records successfully")
            
            return {
                'success': True,
                'analyzed_count': analyzed_count,
                'total_count': len(records)
            }
            
        except Exception as e:
            logger.error(f"Error processing records needing analysis: {str(e)}")
            return {'success': False, 'error': str(e)} 