import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    # Gmail API Configuration
    GMAIL_CLIENT_SECRET_FILE = os.getenv('GMAIL_CLIENT_SECRET_FILE', 'client_secret.json.json')
    GMAIL_TOKEN_FILE = os.getenv('GMAIL_TOKEN_FILE', 'token.json')
    GMAIL_SCOPES = [
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/gmail.modify'
    ]
    
    # MongoDB Configuration
    MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
    MONGODB_DATABASE = os.getenv('MONGODB_DATABASE', 'medmaestro_gmail_agent')
    
    # LLM Configuration
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
    
    # Self-hosted LLM Configuration
    SELF_HOSTED_LLM_URL = os.getenv('SELF_HOSTED_LLM_URL')  # e.g., http://192.168.1.100
    SELF_HOSTED_LLM_PORT = os.getenv('SELF_HOSTED_LLM_PORT', '8000')
    USE_SELF_HOSTED_LLM = os.getenv('USE_SELF_HOSTED_LLM', 'True').lower() == 'true'
    
    # Webhook Configuration
    WEBHOOK_URL = os.getenv('WEBHOOK_URL')
    WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', 'default_webhook_secret')
    
    # Flask Configuration
    FLASK_PORT = int(os.getenv('FLASK_PORT', 5000))
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    # Medical Email Processing Configuration
    PDF_STORAGE_PATH = os.getenv('PDF_STORAGE_PATH', 'pdfs/')
    MAX_PDF_SIZE_MB = int(os.getenv('MAX_PDF_SIZE_MB', 50))
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        required_configs = []
        
        if not cls.OPENAI_API_KEY and not cls.ANTHROPIC_API_KEY and not cls.SELF_HOSTED_LLM_URL:
            required_configs.append("Either OPENAI_API_KEY, ANTHROPIC_API_KEY, or SELF_HOSTED_LLM_URL")
            
        if not os.path.exists(cls.GMAIL_CLIENT_SECRET_FILE):
            required_configs.append(f"Gmail client secret file: {cls.GMAIL_CLIENT_SECRET_FILE}")
            
        if required_configs:
            raise ValueError(f"Missing required configuration: {', '.join(required_configs)}")
        
        return True 