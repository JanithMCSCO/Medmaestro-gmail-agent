#!/usr/bin/env python3
"""
Clear Database Script
Clears all medical records, email history, and PDF files from MongoDB
Use this for testing purposes to start fresh
"""

import logging
from config import Config
from models import DatabaseManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clear_database():
    """Clear all database collections and GridFS files"""
    
    try:
        logger.info("🗑️ Starting database cleanup...")
        
        # Initialize database manager
        db_manager = DatabaseManager()
        
        # Count existing records before deletion
        medical_count = db_manager.medical_records.count_documents({})
        email_count = db_manager.email_history.count_documents({})
        
        # Count GridFS files
        gridfs_files = list(db_manager.fs.find())
        gridfs_count = len(gridfs_files)
        
        logger.info(f"📊 Current database state:")
        logger.info(f"   Medical records: {medical_count}")
        logger.info(f"   Email history: {email_count}")
        logger.info(f"   PDF files (GridFS): {gridfs_count}")
        
        if medical_count == 0 and email_count == 0 and gridfs_count == 0:
            logger.info("✅ Database is already empty!")
            return True
        
        # Ask for confirmation
        print(f"\n⚠️  WARNING: This will permanently delete:")
        print(f"   • {medical_count} medical records")
        print(f"   • {email_count} email history entries")
        print(f"   • {gridfs_count} PDF files")
        print(f"\n❓ Are you sure you want to continue? (type 'yes' to confirm): ", end="")
        
        confirmation = input().strip().lower()
        
        if confirmation != 'yes':
            logger.info("❌ Operation cancelled by user")
            return False
        
        logger.info("🧹 Starting cleanup process...")
        
        # 1. Clear medical records
        if medical_count > 0:
            result = db_manager.medical_records.delete_many({})
            logger.info(f"   ✅ Deleted {result.deleted_count} medical records")
        
        # 2. Clear email history
        if email_count > 0:
            result = db_manager.email_history.delete_many({})
            logger.info(f"   ✅ Deleted {result.deleted_count} email history entries")
        
        # 3. Clear GridFS files (PDFs)
        if gridfs_count > 0:
            deleted_files = 0
            for file_doc in gridfs_files:
                try:
                    db_manager.fs.delete(file_doc._id)
                    deleted_files += 1
                except Exception as e:
                    logger.error(f"   ❌ Failed to delete file {file_doc._id}: {str(e)}")
            
            logger.info(f"   ✅ Deleted {deleted_files} PDF files from GridFS")
        
        # 4. Verify cleanup
        final_medical_count = db_manager.medical_records.count_documents({})
        final_email_count = db_manager.email_history.count_documents({})
        final_gridfs_count = len(list(db_manager.fs.find()))
        
        logger.info(f"\n📊 Final database state:")
        logger.info(f"   Medical records: {final_medical_count}")
        logger.info(f"   Email history: {final_email_count}")
        logger.info(f"   PDF files (GridFS): {final_gridfs_count}")
        
        if final_medical_count == 0 and final_email_count == 0 and final_gridfs_count == 0:
            logger.info("🎉 Database cleanup completed successfully!")
            logger.info("💡 You can now run gmail_to_mongo.py with a fresh database")
            return True
        else:
            logger.warning("⚠️ Some data may not have been cleared completely")
            return False
            
    except Exception as e:
        logger.error(f"❌ Database cleanup failed: {str(e)}")
        import traceback
        logger.error(f"📋 Full error: {traceback.format_exc()}")
        return False

def clear_database_silent():
    """Clear database without confirmation (for automated testing)"""
    
    try:
        logger.info("🗑️ Starting silent database cleanup...")
        
        db_manager = DatabaseManager()
        
        # Clear all collections
        db_manager.medical_records.delete_many({})
        db_manager.email_history.delete_many({})
        
        # Clear GridFS files
        gridfs_files = list(db_manager.fs.find())
        for file_doc in gridfs_files:
            db_manager.fs.delete(file_doc._id)
        
        logger.info("🎉 Silent database cleanup completed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Silent database cleanup failed: {str(e)}")
        return False

def main():
    """Main entry point"""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--silent':
        # Silent mode for automated testing
        success = clear_database_silent()
    else:
        # Interactive mode with confirmation
        success = clear_database()
    
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main() 