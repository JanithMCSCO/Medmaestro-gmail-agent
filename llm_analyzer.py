import logging
import requests
from typing import Dict, Optional
from config import Config

logger = logging.getLogger(__name__)

class LLMAnalyzer:
    """
    Medical document analysis using LLM (OpenAI or Anthropic)
    """
    
    def __init__(self):
        self.openai_client = None
        self.anthropic_client = None
        self.self_hosted_url = None
        
        # Initialize self-hosted LLM first (preferred if configured)
        if Config.USE_SELF_HOSTED_LLM and Config.SELF_HOSTED_LLM_URL:
            self.self_hosted_url = f"{Config.SELF_HOSTED_LLM_URL}:{Config.SELF_HOSTED_LLM_PORT}/v1/chat/completions"
            logger.info(f"Self-hosted LLM configured at: {self.self_hosted_url}")
        
        # Initialize other LLM clients as fallbacks
        if Config.OPENAI_API_KEY:
            try:
                import openai
                self.openai_client = openai.OpenAI(api_key=Config.OPENAI_API_KEY)
                logger.info("OpenAI client initialized")
            except ImportError:
                logger.warning("OpenAI library not available")
        
        if Config.ANTHROPIC_API_KEY:
            try:
                import anthropic
                self.anthropic_client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
                logger.info("Anthropic client initialized")
            except ImportError:
                logger.warning("Anthropic library not available")
        
        if not self.self_hosted_url and not self.openai_client and not self.anthropic_client:
            raise ValueError("No LLM client available. Please configure SELF_HOSTED_LLM_URL, OPENAI_API_KEY or ANTHROPIC_API_KEY.")
    
    def analyze_medical_documents(
        self, 
        collated_text: str, 
        patient_name: str, 
        request_id: str, 
        test_type: str,
        custom_prompt: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Analyze collated medical documents using LLM
        """
        
        if custom_prompt:
            prompt = custom_prompt
        else:
            prompt = self._get_default_medical_analysis_prompt()
        
        # Prepare the analysis request
        analysis_request = f"""
{prompt}

PATIENT INFORMATION:
- Patient Name: {patient_name}
- Request ID: {request_id}
- Test Type: {test_type}

MEDICAL DOCUMENTS TO ANALYZE:
{collated_text}

Please provide your analysis below:
"""
        
        # Try self-hosted LLM first, then OpenAI, then Anthropic
        if self.self_hosted_url:
            try:
                result = self._analyze_with_self_hosted(collated_text, patient_name, request_id, test_type)
                if result['success']:
                    return result
            except Exception as e:
                logger.error(f"Self-hosted LLM analysis failed: {str(e)}")
        
        if self.openai_client:
            try:
                result = self._analyze_with_openai(analysis_request)
                if result['success']:
                    return result
            except Exception as e:
                logger.error(f"OpenAI analysis failed: {str(e)}")
        
        if self.anthropic_client:
            try:
                result = self._analyze_with_anthropic(analysis_request)
                if result['success']:
                    return result
            except Exception as e:
                logger.error(f"Anthropic analysis failed: {str(e)}")
        
        # If all failed
        return {
            'analysis': '',
            'success': False,
            'error': 'All LLM providers failed',
            'provider': 'none'
        }
    
    def _analyze_with_self_hosted(
        self, 
        collated_text: str, 
        patient_name: str, 
        request_id: str, 
        test_type: str
    ) -> Dict[str, str]:
        """Analyze using self-hosted LLM with your custom prompt"""
        try:
            # Your custom system prompt
            system_content = "You are a helpful medical assistant to a medical professional. Provide detailed responses to the questions that are asked of you. The upcoming text is a combination of results from a Blood test report and a CT scan. I want you to use your deep medical knowledge to help diagnose the patient's condition based on the information in the reports"
            
            # Prepare the request payload exactly as per your curl command
            payload = {
                "messages": [
                    {
                        "role": "system", 
                        "content": system_content
                    },
                    {
                        "role": "user", 
                        "content": collated_text
                    }
                ],
                "max_tokens": 400,
                "temperature": 0.7,
                "top_p": 0.9,
                "repetition_penalty": 1.1
            }
            
            # Set headers as per your curl command
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            # Make the API call
            response = requests.post(
                self.self_hosted_url,
                json=payload,
                headers=headers,
                timeout=60  # 60 second timeout
            )
            
            if response.status_code == 200:
                response_data = response.json()
                
                # Extract the analysis text from the response
                # Assuming the response follows OpenAI-like format
                if 'choices' in response_data and len(response_data['choices']) > 0:
                    analysis_text = response_data['choices'][0]['message']['content'].strip()
                else:
                    # Fallback for different response formats
                    analysis_text = str(response_data.get('response', response_data))
                
                return {
                    'analysis': analysis_text,
                    'success': True,
                    'error': None,
                    'provider': 'self-hosted',
                    'model': 'self-hosted-llm',
                    'patient_name': patient_name,
                    'request_id': request_id,
                    'test_type': test_type
                }
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                logger.error(f"Self-hosted LLM API error: {error_msg}")
                return {
                    'analysis': '',
                    'success': False,
                    'error': error_msg,
                    'provider': 'self-hosted'
                }
                
        except requests.exceptions.Timeout:
            error_msg = "Request timed out"
            logger.error(f"Self-hosted LLM timeout: {error_msg}")
            return {
                'analysis': '',
                'success': False,
                'error': error_msg,
                'provider': 'self-hosted'
            }
        except requests.exceptions.ConnectionError:
            error_msg = f"Connection failed to {self.self_hosted_url}"
            logger.error(f"Self-hosted LLM connection error: {error_msg}")
            return {
                'analysis': '',
                'success': False,
                'error': error_msg,
                'provider': 'self-hosted'
            }
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Self-hosted LLM API error: {error_msg}")
            return {
                'analysis': '',
                'success': False,
                'error': error_msg,
                'provider': 'self-hosted'
            }

    def _analyze_with_openai(self, prompt: str) -> Dict[str, str]:
        """Analyze using OpenAI GPT"""
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4-turbo-preview",  # Use GPT-4 for medical analysis
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a medical AI assistant specialized in analyzing medical test results and documents. Provide thorough, accurate, and professional analysis while noting that this is for informational purposes and should not replace professional medical advice."
                    },
                    {"role": "user", "content": prompt}
                ],
                max_tokens=4000,
                temperature=0.1  # Low temperature for consistent medical analysis
            )
            
            analysis_text = response.choices[0].message.content.strip()
            
            return {
                'analysis': analysis_text,
                'success': True,
                'error': None,
                'provider': 'openai',
                'model': 'gpt-4-turbo-preview',
                'tokens_used': response.usage.total_tokens if hasattr(response, 'usage') else None
            }
            
        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            return {
                'analysis': '',
                'success': False,
                'error': str(e),
                'provider': 'openai'
            }
    
    def _analyze_with_anthropic(self, prompt: str) -> Dict[str, str]:
        """Analyze using Anthropic Claude"""
        try:
            response = self.anthropic_client.messages.create(
                model="claude-3-sonnet-20240229",  # Use Claude Sonnet for medical analysis
                max_tokens=4000,
                temperature=0.1,
                system="You are a medical AI assistant specialized in analyzing medical test results and documents. Provide thorough, accurate, and professional analysis while noting that this is for informational purposes and should not replace professional medical advice.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            analysis_text = response.content[0].text.strip()
            
            return {
                'analysis': analysis_text,
                'success': True,
                'error': None,
                'provider': 'anthropic',
                'model': 'claude-3-sonnet-20240229',
                'tokens_used': response.usage.input_tokens + response.usage.output_tokens if hasattr(response, 'usage') else None
            }
            
        except Exception as e:
            logger.error(f"Anthropic API error: {str(e)}")
            return {
                'analysis': '',
                'success': False,
                'error': str(e),
                'provider': 'anthropic'
            }
    
    def _get_default_medical_analysis_prompt(self) -> str:
        """Get the default prompt for medical document analysis"""
        return """
You are a medical AI assistant analyzing medical documents and test results. Please provide a comprehensive analysis of the provided medical documents.

Your analysis should include:

1. **DOCUMENT SUMMARY**
   - Brief overview of the documents provided
   - Types of tests/procedures documented
   - Date range of the medical records

2. **KEY FINDINGS**
   - Important test results and values
   - Any abnormal or concerning findings
   - Trends or changes between different documents (if multiple)

3. **CLINICAL INTERPRETATION**
   - What the results might indicate
   - Potential diagnoses or conditions suggested by the findings
   - Areas that may require further investigation

4. **RECOMMENDATIONS**
   - Suggested follow-up actions
   - Additional tests that might be needed
   - Monitoring recommendations

5. **IMPORTANT NOTES**
   - Any urgent or time-sensitive findings
   - Limitations of the analysis
   - Reminder that this analysis is for informational purposes only

Please structure your response clearly with these sections. Be thorough but concise, and always emphasize that this analysis should not replace professional medical consultation.

IMPORTANT: If any values appear critical or life-threatening, clearly highlight them in your analysis.
"""
    
    def analyze_single_document(
        self, 
        text: str, 
        patient_name: str, 
        request_id: str, 
        test_type: str
    ) -> Dict[str, str]:
        """
        Analyze a single medical document (for non-duplicate cases)
        """
        
        prompt = f"""
You are a medical AI assistant. Please analyze this single medical document and provide a brief summary.

PATIENT INFORMATION:
- Patient Name: {patient_name}
- Request ID: {request_id}
- Test Type: {test_type}

DOCUMENT CONTENT:
{text}

Please provide:
1. A brief summary of the document
2. Key findings or results
3. Any notable observations
4. Recommendation for follow-up if needed

Keep the analysis concise but informative.
"""
        
        # Use the same LLM providers but with a simpler prompt
        if self.self_hosted_url:
            try:
                result = self._analyze_with_self_hosted(text, patient_name, request_id, test_type)
                if result['success']:
                    return result
            except Exception as e:
                logger.error(f"Self-hosted LLM single document analysis failed: {str(e)}")
        
        if self.openai_client:
            try:
                result = self._analyze_with_openai(prompt)
                if result['success']:
                    return result
            except Exception as e:
                logger.error(f"OpenAI single document analysis failed: {str(e)}")
        
        if self.anthropic_client:
            try:
                result = self._analyze_with_anthropic(prompt)
                if result['success']:
                    return result
            except Exception as e:
                logger.error(f"Anthropic single document analysis failed: {str(e)}")
        
        return {
            'analysis': 'Analysis failed - no LLM provider available',
            'success': False,
            'error': 'All LLM providers failed',
            'provider': 'none'
        } 