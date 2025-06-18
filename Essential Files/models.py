from datetime import datetime
from typing import List, Optional
from pymongo import MongoClient
from bson import ObjectId
import gridfs
from config import Config

class DatabaseManager:
    def __init__(self):
        self.client = MongoClient(Config.MONGODB_URI)
        self.db = self.client[Config.MONGODB_DATABASE]
        self.fs = gridfs.GridFS(self.db)
        self.medical_records = self.db.medical_records
        self.email_history = self.db.email_history
        
        # Create indexes for efficient querying
        self.medical_records.create_index([("request_id", 1), ("patient_name", 1)], unique=True)
        self.email_history.create_index([("message_id", 1)], unique=True)
        self.email_history.create_index([("processed_at", 1)])

class MedicalRecord:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.collection = db_manager.medical_records

    def create_or_update(
        self,
        request_id: str,
        patient_name: str,
        test_type: str,
        pdf_content: bytes,
        extracted_text: str,
        email_message_id: str,
        original_filename: str,
        test_summary: str = ""
    ) -> dict:
        """Create new record or update existing one with collated PDF text"""
        
        existing_record = self.collection.find_one({
            "request_id": request_id,
            "patient_name": patient_name
        })
        
        # Store PDF in GridFS
        pdf_file_id = self.db_manager.fs.put(
            pdf_content,
            filename=f"{request_id}_{patient_name}_{datetime.now().isoformat()}_{original_filename}",
            metadata={
                "request_id": request_id,
                "patient_name": patient_name,
                "test_type": test_type,
                "original_filename": original_filename,
                "email_message_id": email_message_id
            }
        )
        
        if existing_record:
            # Update existing record - collate texts
            collated_text = existing_record.get("extracted_text", "") + "\n\n--- NEW DOCUMENT ---\n\n" + extracted_text
            
            # Update test summary (combine if multiple summaries)
            existing_summary = existing_record.get("test_summary", "")
            updated_summary = existing_summary
            if test_summary:
                if existing_summary:
                    updated_summary = existing_summary + " | " + test_summary
                else:
                    updated_summary = test_summary
            
            update_data = {
                "$push": {
                    "pdf_files": {
                        "file_id": pdf_file_id,
                        "filename": original_filename,
                        "email_message_id": email_message_id,
                        "uploaded_at": datetime.now(),
                        "test_summary": test_summary,
                        "test_type": test_type
                    },
                    "email_message_ids": email_message_id
                },
                "$set": {
                    "extracted_text": collated_text,
                    "test_summary": updated_summary,
                    "test_type": test_type,  # Update in case it changed
                    "last_updated": datetime.now(),
                    "needs_llm_analysis": True  # Flag for LLM processing
                }
            }
            
            result = self.collection.update_one(
                {"_id": existing_record["_id"]},
                update_data
            )
            
            return {
                "record_id": str(existing_record["_id"]),
                "action": "updated",
                "is_duplicate": True,
                "collated_text": collated_text
            }
        else:
            # Create new record
            new_record = {
                "request_id": request_id,
                "patient_name": patient_name,
                "test_type": test_type,
                "extracted_text": extracted_text,
                "test_summary": test_summary,
                "pdf_files": [{
                    "file_id": pdf_file_id,
                    "filename": original_filename,
                    "email_message_id": email_message_id,
                    "uploaded_at": datetime.now(),
                    "test_summary": test_summary,
                    "test_type": test_type
                }],
                "email_message_ids": [email_message_id],
                "created_at": datetime.now(),
                "last_updated": datetime.now(),
                "needs_llm_analysis": False
            }
            
            result = self.collection.insert_one(new_record)
            
            return {
                "record_id": str(result.inserted_id),
                "action": "created",
                "is_duplicate": False,
                "collated_text": extracted_text
            }
    
    def get_record(self, request_id: str, patient_name: str) -> Optional[dict]:
        """Get existing medical record"""
        return self.collection.find_one({
            "request_id": request_id,
            "patient_name": patient_name
        })
    
    def get_records_needing_analysis(self) -> List[dict]:
        """Get all records that need LLM analysis"""
        return list(self.collection.find({"needs_llm_analysis": True}))
    
    def mark_analysis_complete(self, record_id: str, analysis_result: str):
        """Mark record as analyzed and store the result"""
        self.collection.update_one(
            {"_id": ObjectId(record_id)},
            {
                "$set": {
                    "needs_llm_analysis": False,
                    "llm_analysis": analysis_result,
                    "analysis_completed_at": datetime.now()
                }
            }
        )

class EmailHistory:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.collection = db_manager.email_history
    
    def add_processed_email(
        self,
        message_id: str,
        subject: str,
        sender: str,
        request_id: str,
        patient_name: str,
        test_type: str,
        has_pdf: bool,
        pdf_filename: Optional[str] = None,
        processing_status: str = "success",
        error_message: Optional[str] = None
    ):
        """Record that an email has been processed"""
        email_record = {
            "message_id": message_id,
            "subject": subject,
            "sender": sender,
            "request_id": request_id,
            "patient_name": patient_name,
            "test_type": test_type,
            "has_pdf": has_pdf,
            "pdf_filename": pdf_filename,
            "processing_status": processing_status,
            "error_message": error_message,
            "processed_at": datetime.now()
        }
        
        self.collection.insert_one(email_record)
    
    def is_email_processed(self, message_id: str) -> bool:
        """Check if email has already been processed"""
        return self.collection.find_one({"message_id": message_id}) is not None 