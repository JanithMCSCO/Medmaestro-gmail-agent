#!/usr/bin/env python3
"""
MongoDB Medical Records Viewer

View medical records stored in MongoDB with all key information.
"""

import logging
from datetime import datetime
from models import DatabaseManager
from bson import ObjectId

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MongoRecordViewer:
    """View medical records in MongoDB"""
    
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.medical_records = self.db_manager.medical_records
    
    def view_all_records(self):
        """View all medical records"""
        
        logger.info("📋 MongoDB Medical Records")
        logger.info("=" * 60)
        
        try:
            records = list(self.medical_records.find().sort("created_at", -1))
            
            if not records:
                logger.info("📭 No medical records found in database")
                return
            
            logger.info(f"✅ Found {len(records)} medical record(s)\n")
            
            for i, record in enumerate(records, 1):
                self.print_record_summary(record, i)
                print()
            
        except Exception as e:
            logger.error(f"❌ Error viewing records: {str(e)}")
    
    def print_record_summary(self, record, index):
        """Print a summary of a single record"""
        
        record_id = str(record['_id'])
        request_id = record.get('request_id', 'N/A')
        patient_name = record.get('patient_name', 'N/A')
        test_type = record.get('test_type', 'N/A')
        test_summary = record.get('test_summary', 'N/A')
        
        # PDF file info
        pdf_files = record.get('pdf_files', [])
        pdf_count = len(pdf_files)
        
        # Dates
        created_at = record.get('created_at', datetime.now())
        last_updated = record.get('last_updated', datetime.now())
        
        # Text info
        extracted_text = record.get('extracted_text', '')
        text_length = len(extracted_text)
        
        # Analysis status
        needs_analysis = record.get('needs_llm_analysis', False)
        has_analysis = 'llm_analysis' in record
        
        print(f"📄 Record {index} (ID: {record_id[:8]}...)")
        print(f"   🆔 Request ID: {request_id}")
        print(f"   👤 Patient: {patient_name}")
        print(f"   🧪 Test Type: {test_type}")
        print(f"   📝 Test Summary: {test_summary[:100]}{'...' if len(test_summary) > 100 else ''}")
        print(f"   📎 PDF Files: {pdf_count}")
        
        # Show PDF filenames
        if pdf_files:
            for j, pdf_file in enumerate(pdf_files, 1):
                filename = pdf_file.get('filename', 'unknown.pdf')
                uploaded_at = pdf_file.get('uploaded_at', 'unknown')
                print(f"      {j}. {filename} (uploaded: {uploaded_at})")
        
        print(f"   📊 Extracted Text: {text_length} characters")
        print(f"   📅 Created: {created_at}")
        print(f"   🔄 Updated: {last_updated}")
        print(f"   🤖 Needs Analysis: {'Yes' if needs_analysis else 'No'}")
        print(f"   ✅ Has Analysis: {'Yes' if has_analysis else 'No'}")
    
    def view_record_details(self, record_id: str):
        """View full details of a specific record"""
        
        try:
            record = self.medical_records.find_one({"_id": ObjectId(record_id)})
            
            if not record:
                logger.error(f"❌ Record with ID {record_id} not found")
                return
            
            logger.info(f"📄 Detailed View - Record ID: {record_id}")
            logger.info("=" * 60)
            
            # Basic info
            print(f"🆔 Request ID: {record.get('request_id', 'N/A')}")
            print(f"👤 Patient: {record.get('patient_name', 'N/A')}")
            print(f"🧪 Test Type: {record.get('test_type', 'N/A')}")
            print(f"📅 Created: {record.get('created_at', 'N/A')}")
            print(f"🔄 Updated: {record.get('last_updated', 'N/A')}")
            print()
            
            # Test Summary
            test_summary = record.get('test_summary', '')
            print(f"📝 Test Summary:")
            print(f"{test_summary}")
            print()
            
            # Clinical Interpretation (extracted text)
            extracted_text = record.get('extracted_text', '')
            print(f"📋 Clinical Interpretation ({len(extracted_text)} characters):")
            print("-" * 40)
            if len(extracted_text) > 500:
                print(f"{extracted_text[:500]}...")
                print(f"\n[Truncated - showing first 500 of {len(extracted_text)} characters]")
            else:
                print(extracted_text)
            print("-" * 40)
            print()
            
            # PDF Files
            pdf_files = record.get('pdf_files', [])
            print(f"📎 PDF Files ({len(pdf_files)}):")
            for i, pdf_file in enumerate(pdf_files, 1):
                print(f"   {i}. {pdf_file.get('filename', 'unknown.pdf')}")
                print(f"      File ID: {pdf_file.get('file_id', 'N/A')}")
                print(f"      Email ID: {pdf_file.get('email_message_id', 'N/A')}")
                print(f"      Uploaded: {pdf_file.get('uploaded_at', 'N/A')}")
            print()
            
            # LLM Analysis
            if 'llm_analysis' in record:
                analysis = record['llm_analysis']
                print(f"🤖 LLM Analysis:")
                print("-" * 40)
                if len(analysis) > 300:
                    print(f"{analysis[:300]}...")
                    print(f"\n[Truncated - showing first 300 characters]")
                else:
                    print(analysis)
                print("-" * 40)
            else:
                print(f"🤖 LLM Analysis: Not performed yet")
            
        except Exception as e:
            logger.error(f"❌ Error viewing record details: {str(e)}")
    
    def search_by_patient(self, patient_name: str):
        """Search records by patient name"""
        
        try:
            records = list(self.medical_records.find({
                "patient_name": {"$regex": patient_name, "$options": "i"}
            }).sort("created_at", -1))
            
            if not records:
                logger.info(f"📭 No records found for patient: {patient_name}")
                return
            
            logger.info(f"🔍 Records for patient '{patient_name}' ({len(records)} found)")
            logger.info("=" * 50)
            
            for i, record in enumerate(records, 1):
                self.print_record_summary(record, i)
                print()
                
        except Exception as e:
            logger.error(f"❌ Error searching records: {str(e)}")
    
    def search_by_request_id(self, request_id: str):
        """Search records by request ID"""
        
        try:
            records = list(self.medical_records.find({
                "request_id": request_id
            }).sort("created_at", -1))
            
            if not records:
                logger.info(f"📭 No records found for Request ID: {request_id}")
                return
            
            logger.info(f"🔍 Records for Request ID '{request_id}' ({len(records)} found)")
            logger.info("=" * 50)
            
            for i, record in enumerate(records, 1):
                self.print_record_summary(record, i)
                print()
                
        except Exception as e:
            logger.error(f"❌ Error searching records: {str(e)}")

def main():
    """Main entry point"""
    import sys
    
    viewer = MongoRecordViewer()
    
    if len(sys.argv) < 2:
        # No arguments - show all records
        viewer.view_all_records()
    else:
        command = sys.argv[1].lower()
        
        if command == "details" and len(sys.argv) > 2:
            # View specific record details
            record_id = sys.argv[2]
            viewer.view_record_details(record_id)
        
        elif command == "patient" and len(sys.argv) > 2:
            # Search by patient name
            patient_name = " ".join(sys.argv[2:])
            records = list(viewer.medical_records.find({
                "patient_name": {"$regex": patient_name, "$options": "i"}
            }).sort("created_at", -1))
            
            if records:
                logger.info(f"🔍 Records for patient '{patient_name}' ({len(records)} found)")
                for i, record in enumerate(records, 1):
                    viewer.print_record_summary(record, i)
                    print()
            else:
                logger.info(f"📭 No records found for patient: {patient_name}")
        
        elif command == "request" and len(sys.argv) > 2:
            # Search by request ID
            request_id = sys.argv[2]
            records = list(viewer.medical_records.find({
                "request_id": request_id
            }).sort("created_at", -1))
            
            if records:
                logger.info(f"🔍 Records for Request ID '{request_id}' ({len(records)} found)")
                for i, record in enumerate(records, 1):
                    viewer.print_record_summary(record, i)
                    print()
            else:
                logger.info(f"📭 No records found for Request ID: {request_id}")
        
        else:
            print("Usage:")
            print("  python view_mongo_records.py                    # View all records")
            print("  python view_mongo_records.py details <id>       # View specific record")
            print("  python view_mongo_records.py patient <name>     # Search by patient")
            print("  python view_mongo_records.py request <id>       # Search by request ID")

if __name__ == '__main__':
    main() 