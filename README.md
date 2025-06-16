# Medical Gmail Agent

An AI-powered system for automated medical email processing that reads Gmail emails, extracts text from PDF attachments, stores data in MongoDB, and performs intelligent analysis using LLMs.

## 🏥 Features

- **Real-time Email Processing**: Gmail push notifications for instant processing
- **PDF Text Extraction**: Robust extraction from medical PDFs with multiple fallback methods
- **Medical Data Parsing**: Intelligent extraction of Request ID, patient name, and test type from email subjects
- **MongoDB Storage**: Secure storage of medical records with GridFS for PDF files
- **Duplicate Detection**: Automatic collation of multiple documents for the same patient/request
- **LLM Analysis**: AI-powered analysis of collated medical documents
- **RESTful API**: Flask-based webhook server with manual processing endpoints

## 🏗️ System Architecture

The system consists of:
1. **Gmail Service**: Email reading and PDF extraction
2. **PDF Extractor**: Text extraction with fallback methods
3. **Database Models**: MongoDB storage with GridFS
4. **Email Processor**: Main orchestration logic
5. **LLM Analyzer**: AI-powered medical document analysis
6. **Webhook Server**: Real-time processing via Flask

## 📋 Prerequisites

1. **Google Cloud Project** with Gmail API enabled
2. **MongoDB** instance (local or cloud)
3. **LLM API Key** (OpenAI or Anthropic)
4. **Python 3.8+**

## 🚀 Quick Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
python main.py setup --create-env
# Edit .env file with your API keys and settings
```

### 3. Validate Setup
```bash
python main.py setup --validate
```

### 4. Run the System
```bash
# Real-time processing
python main.py webhook

# Or batch processing
python main.py batch --days 1
```

## 📧 Email Format Requirements

Expected email subject formats:
- `Request ID: REQ123 | Test: Blood Work | Patient: John Doe`
- `REQ456 - MRI Scan - Jane Smith`
- `Request REQ789 Blood Test for Patient Mary Johnson`

## 🔧 Usage Commands

```bash
# Start webhook server for real-time processing
python main.py webhook

# Process recent emails (batch mode)
python main.py batch --days 7

# Test single email
python main.py test <message-id>

# Setup commands
python main.py setup --validate
python main.py setup --create-env
python main.py setup --setup-push
```

## 📊 Features

- **Duplicate Handling**: Automatically collates PDFs for same patient+request ID
- **LLM Analysis**: Triggers AI analysis when duplicates are detected
- **Error Recovery**: Robust error handling and logging
- **Security**: Webhook signature verification and secure API access
- **Monitoring**: Health checks and processing statistics

## 🔐 Configuration

Set up your `.env` file with:
- Gmail API credentials
- MongoDB connection string
- OpenAI or Anthropic API key
- Webhook URL and secret

## 📄 License

MIT License - see LICENSE file for details.

---

**⚠️ Medical Disclaimer**: This tool is for informational purposes only and should not replace professional medical advice. 