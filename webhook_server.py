import logging
import base64
import json
import hmac
import hashlib
from flask import Flask, request, jsonify
from threading import Thread
from email_processor import MedicalEmailProcessor
from config import Config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
email_processor = MedicalEmailProcessor()

def verify_webhook_signature(payload, signature, secret):
    """
    Verify Gmail webhook signature for security
    """
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)

@app.route('/webhook/gmail', methods=['POST'])
def gmail_webhook():
    """
    Handle Gmail push notifications
    """
    try:
        # Get the raw payload
        payload = request.get_data()
        
        # Verify signature if secret is configured
        if Config.WEBHOOK_SECRET and Config.WEBHOOK_SECRET != 'default_webhook_secret':
            signature = request.headers.get('X-Goog-Channel-Token', '')
            if not verify_webhook_signature(payload, signature, Config.WEBHOOK_SECRET):
                logger.warning("Invalid webhook signature")
                return jsonify({'error': 'Invalid signature'}), 401
        
        # Parse the notification
        try:
            notification_data = json.loads(payload.decode('utf-8'))
        except json.JSONDecodeError:
            logger.error("Invalid JSON in webhook payload")
            return jsonify({'error': 'Invalid JSON'}), 400
        
        # Extract message from Pub/Sub format
        if 'message' in notification_data:
            message_data = notification_data['message']
            if 'data' in message_data:
                # Decode base64 data
                try:
                    decoded_data = base64.b64decode(message_data['data']).decode('utf-8')
                    gmail_notification = json.loads(decoded_data)
                except Exception as e:
                    logger.error(f"Error decoding Gmail notification data: {str(e)}")
                    return jsonify({'error': 'Invalid notification data'}), 400
            else:
                gmail_notification = message_data
        else:
            gmail_notification = notification_data
        
        logger.info(f"Received Gmail notification: {gmail_notification}")
        
        # Extract email details from notification
        email_address = gmail_notification.get('emailAddress', '')
        history_id = gmail_notification.get('historyId', '')
        
        if not history_id:
            logger.warning("No historyId in Gmail notification")
            return jsonify({'error': 'No historyId provided'}), 400
        
        # Process new emails in background
        thread = Thread(
            target=process_gmail_notification_async,
            args=(history_id, email_address)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({'status': 'success', 'message': 'Notification received'}), 200
        
    except Exception as e:
        logger.error(f"Error processing Gmail webhook: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

def process_gmail_notification_async(history_id: str, email_address: str):
    """
    Process Gmail notification asynchronously
    """
    try:
        logger.info(f"Processing Gmail notification for {email_address}, historyId: {history_id}")
        
        # Get recent medical emails (last 1 day) and process them
        result = email_processor.process_recent_emails(days_back=1)
        
        if result['success']:
            logger.info(f"Successfully processed {result['processed_count']} emails from notification")
        else:
            logger.error(f"Error processing emails from notification: {result.get('error', 'Unknown error')}")
        
        # Also process any records that need LLM analysis
        analysis_result = email_processor.process_records_needing_analysis()
        if analysis_result['success'] and analysis_result['analyzed_count'] > 0:
            logger.info(f"Analyzed {analysis_result['analyzed_count']} pending records")
            
    except Exception as e:
        logger.error(f"Error in async Gmail notification processing: {str(e)}")

@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint
    """
    return jsonify({
        'status': 'healthy',
        'service': 'Medical Gmail Agent',
        'timestamp': logger.manager.loggerDict
    }), 200

@app.route('/process-recent', methods=['POST'])
def process_recent_emails():
    """
    Manual endpoint to process recent emails
    """
    try:
        days_back = request.json.get('days_back', 1) if request.is_json else 1
        
        result = email_processor.process_recent_emails(days_back=days_back)
        
        return jsonify(result), 200 if result['success'] else 500
        
    except Exception as e:
        logger.error(f"Error in manual email processing: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/analyze-pending', methods=['POST'])
def analyze_pending_records():
    """
    Manual endpoint to analyze pending records
    """
    try:
        result = email_processor.process_records_needing_analysis()
        
        return jsonify(result), 200 if result['success'] else 500
        
    except Exception as e:
        logger.error(f"Error in manual analysis: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/stats', methods=['GET'])
def get_stats():
    """
    Get processing statistics
    """
    try:
        # This would query the database for statistics
        # For now, return a placeholder
        stats = {
            'total_emails_processed': 'N/A - Implement database query',
            'total_pdfs_extracted': 'N/A - Implement database query',
            'total_llm_analyses': 'N/A - Implement database query',
            'last_processing_time': 'N/A - Implement database query'
        }
        
        return jsonify(stats), 200
        
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/test-email', methods=['POST'])
def test_single_email():
    """
    Test endpoint to process a specific email by message ID
    """
    try:
        if not request.is_json:
            return jsonify({'error': 'JSON payload required'}), 400
        
        message_id = request.json.get('message_id')
        if not message_id:
            return jsonify({'error': 'message_id is required'}), 400
        
        result = email_processor.process_single_email(message_id)
        
        return jsonify(result), 200 if result['success'] else 500
        
    except Exception as e:
        logger.error(f"Error in test email processing: {str(e)}")
        return jsonify({'error': str(e)}), 500

def run_server():
    """
    Run the Flask webhook server
    """
    try:
        # Validate configuration
        Config.validate()
        
        logger.info(f"Starting Medical Gmail Agent webhook server on port {Config.FLASK_PORT}")
        logger.info(f"Webhook URL should be: {Config.WEBHOOK_URL or 'Not configured'}")
        
        app.run(
            host='0.0.0.0',
            port=Config.FLASK_PORT,
            debug=Config.FLASK_DEBUG,
            threaded=True
        )
        
    except Exception as e:
        logger.error(f"Error starting server: {str(e)}")
        raise

if __name__ == '__main__':
    run_server() 