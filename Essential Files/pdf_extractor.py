import io
import logging
from typing import Optional, Dict
import PyPDF2
import pdfplumber
from config import Config

logger = logging.getLogger(__name__)

class PDFTextExtractor:
    """
    Medical PDF text extraction service with multiple fallback methods
    """
    
    def __init__(self):
        self.max_file_size = Config.MAX_PDF_SIZE_MB * 1024 * 1024  # Convert to bytes
    
    def extract_text(self, pdf_data: bytes, filename: str = "unknown.pdf") -> Dict[str, str]:
        """
        Extract text from PDF using multiple methods for robustness
        Returns dict with extracted text and metadata
        """
        
        # Check file size
        if len(pdf_data) > self.max_file_size:
            logger.warning(f"PDF {filename} exceeds maximum size ({len(pdf_data)} bytes)")
            return {
                'text': '',
                'extraction_method': 'failed',
                'error': f'File size {len(pdf_data)} bytes exceeds maximum {self.max_file_size} bytes',
                'success': False
            }
        
        # Try multiple extraction methods
        extraction_methods = [
            ('pdfplumber', self._extract_with_pdfplumber),
            ('pypdf2', self._extract_with_pypdf2),
        ]
        
        for method_name, method_func in extraction_methods:
            try:
                text = method_func(pdf_data)
                if text and text.strip():
                    logger.info(f"Successfully extracted text from {filename} using {method_name}")
                    return {
                        'text': self._clean_text(text),
                        'extraction_method': method_name,
                        'error': None,
                        'success': True,
                        'text_length': len(text.strip()),
                        'filename': filename
                    }
            except Exception as e:
                logger.warning(f"Failed to extract text from {filename} using {method_name}: {str(e)}")
                continue
        
        # If all methods failed
        logger.error(f"All extraction methods failed for {filename}")
        return {
            'text': '',
            'extraction_method': 'failed',
            'error': 'All extraction methods failed',
            'success': False,
            'filename': filename
        }
    
    def _extract_with_pdfplumber(self, pdf_data: bytes) -> str:
        """Extract text using pdfplumber (better for complex layouts)"""
        text_content = []
        
        with pdfplumber.open(io.BytesIO(pdf_data)) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                try:
                    page_text = page.extract_text()
                    if page_text:
                        text_content.append(f"--- Page {page_num} ---\n{page_text}")
                    
                    # Also try to extract tables
                    tables = page.extract_tables()
                    for table_num, table in enumerate(tables, 1):
                        if table:
                            table_text = self._table_to_text(table)
                            if table_text:
                                text_content.append(f"\n--- Page {page_num} Table {table_num} ---\n{table_text}")
                                
                except Exception as e:
                    logger.warning(f"Error extracting page {page_num}: {str(e)}")
                    continue
        
        return '\n\n'.join(text_content)
    
    def _extract_with_pypdf2(self, pdf_data: bytes) -> str:
        """Extract text using PyPDF2 (fallback method)"""
        text_content = []
        
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_data))
        
        for page_num, page in enumerate(pdf_reader.pages, 1):
            try:
                page_text = page.extract_text()
                if page_text:
                    text_content.append(f"--- Page {page_num} ---\n{page_text}")
            except Exception as e:
                logger.warning(f"Error extracting page {page_num} with PyPDF2: {str(e)}")
                continue
        
        return '\n\n'.join(text_content)
    
    def _table_to_text(self, table: list) -> str:
        """Convert extracted table to readable text format"""
        if not table:
            return ""
        
        table_lines = []
        for row in table:
            if row:
                # Filter out None values and convert to string
                clean_row = [str(cell) if cell is not None else "" for cell in row]
                table_lines.append(" | ".join(clean_row))
        
        return "\n".join(table_lines)
    
    def _clean_text(self, text: str) -> str:
        """Clean extracted text for better processing"""
        if not text:
            return ""
        
        # Remove excessive whitespace
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            cleaned_line = ' '.join(line.split())  # Normalize whitespace
            if cleaned_line:  # Skip empty lines
                cleaned_lines.append(cleaned_line)
        
        # Join lines and normalize paragraph breaks
        cleaned_text = '\n'.join(cleaned_lines)
        
        # Remove multiple consecutive newlines
        import re
        cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text)
        
        return cleaned_text.strip()
    
    def validate_medical_content(self, text: str) -> Dict[str, bool]:
        """
        Basic validation to check if extracted text contains medical content
        """
        medical_keywords = [
            'patient', 'diagnosis', 'test', 'result', 'medical', 'doctor', 'physician', 
            'laboratory', 'blood', 'urine', 'mri', 'ct', 'scan', 'x-ray', 'ultrasound',
            'biopsy', 'pathology', 'radiology', 'clinical', 'specimen', 'sample',
            'normal', 'abnormal', 'negative', 'positive', 'mg/dl', 'mmhg', 'bpm'
        ]
        
        text_lower = text.lower()
        found_keywords = [keyword for keyword in medical_keywords if keyword in text_lower]
        
        # Check for common medical patterns
        has_medical_patterns = bool(
            # Date patterns
            re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', text) or
            # Medical reference ranges
            re.search(r'\d+\.?\d*\s*-\s*\d+\.?\d*', text) or
            # Medical units
            re.search(r'\d+\.?\d*\s*(mg|ml|dl|mm|cm|kg|lbs|bpm|mmhg)', text, re.IGNORECASE)
        )
        
        return {
            'has_medical_keywords': len(found_keywords) >= 2,
            'found_keywords': found_keywords,
            'has_medical_patterns': has_medical_patterns,
            'is_likely_medical': len(found_keywords) >= 2 or has_medical_patterns,
            'keyword_count': len(found_keywords)
        } 