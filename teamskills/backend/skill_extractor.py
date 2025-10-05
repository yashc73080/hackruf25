import json
import os
import sys
import tempfile
from typing import List, Dict, Optional, Union
import google.generativeai as genai
from dotenv import load_dotenv

# Handle imports - try relative first, then absolute
try:
    from .github_scraper import summarize_user
    from .resume_scraper import extract_with_pdfplumber, extract_with_gcv
except ImportError:
    # If relative imports fail, try absolute imports or add parent to path
    parent_dir = os.path.dirname(os.path.dirname(__file__))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    
    try:
        from backend.github_scraper import summarize_user
        from backend.resume_scraper import extract_with_pdfplumber, extract_with_gcv
    except ImportError:
        # If still failing, import only what we need for testing
        print("⚠️ Warning: Could not import github_scraper and resume_scraper modules")
        print("⚠️ This is normal when running the test function directly")
        
        # Define minimal fallback functions for testing
        def extract_with_pdfplumber(file_path):
            try:
                import pdfplumber
                text = ""
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
                return text.strip()
            except Exception as e:
                print(f"❌ PDFPlumber error: {e}")
                return ""
        
        def extract_with_gcv(file_path):
            print("❌ Google Cloud Vision not available in fallback mode")
            return ""
        
        def summarize_user(username, max_repos=5):
            print("❌ GitHub scraper not available in fallback mode")
            return []

# Load environment variables - check multiple locations
load_dotenv()  # Default behavior
# Also try loading from parent directory
parent_dir = os.path.dirname(os.path.dirname(__file__))
env_local_path = os.path.join(parent_dir, '.env.local')
if os.path.exists(env_local_path):
    load_dotenv(env_local_path)

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
print(f"🔑 GEMINI_API_KEY found: {'Yes' if GEMINI_API_KEY else 'No'}")
if GEMINI_API_KEY:
    print(f"🔑 API Key length: {len(GEMINI_API_KEY)}")
    try:
        configure_fn = getattr(genai, "configure", None)
        if callable(configure_fn):
            configure_fn(api_key=GEMINI_API_KEY)
            print("✅ Gemini API configured successfully")
    except Exception as e:
        print(f"❌ Warning: failed to configure Gemini: {e}")

def extract_text_from_file(file_path: str, threshold: int = 500) -> str:
    """
    Extract text from a resume file (PDF or image) using the resume_scraper logic.
    
    Args:
        file_path: Path to the resume file
        threshold: Minimum text length before falling back to OCR
        
    Returns:
        Extracted text content
    """
    print(f"📄 Extracting text from: {file_path}")
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    ext = os.path.splitext(file_path)[1].lower()
    extracted = ""
    
    try:
        if ext == ".pdf":
            print("📄 Trying pdfplumber extraction...")
            # Try pdfplumber first
            extracted = extract_with_pdfplumber(file_path)
            print(f"📄 PDFPlumber extracted {len(extracted)} characters")
            
            # Fall back to Vision OCR if text is too short
            if len(extracted) < threshold:
                print(f"📄 Text too short ({len(extracted)} < {threshold}), trying Vision OCR...")
                gcv_text = extract_with_gcv(file_path)
                print(f"📄 Vision OCR extracted {len(gcv_text)} characters")
                if len(gcv_text) > len(extracted):
                    extracted = gcv_text
                    print("📄 Using Vision OCR result")
        else:
            print("📄 Using Vision OCR for image file...")
            # For images, use Vision OCR directly
            extracted = extract_with_gcv(file_path)
            print(f"📄 Vision OCR extracted {len(extracted)} characters")
            
    except Exception as e:
        print(f"❌ Error in primary extraction: {e}")
        # Last resort: try Vision OCR
        try:
            print("📄 Trying Vision OCR as fallback...")
            extracted = extract_with_gcv(file_path)
            print(f"📄 Fallback Vision OCR extracted {len(extracted)} characters")
        except Exception as e2:
            print(f"❌ Vision fallback also failed: {e2}")
            raise RuntimeError(f"Failed to extract text: {e}. Vision fallback error: {e2}")
    
    print(f"📄 Final extracted text length: {len(extracted)} characters")
    if len(extracted) > 0:
        print(f"📄 First 200 chars: {extracted[:200]}...")
    
    return extracted

def extract_skills_with_gemini(text_content: str, content_type: str = "mixed") -> Dict:
    """
    Use Gemini API to extract skills, technologies, and keywords from text.
    
    Args:
        text_content: The text to analyze
        content_type: Type of content ("resume", "github", or "mixed")
        
    Returns:
        Dictionary containing extracted skills and keywords
    """
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not found in environment variables")
    
    print(f"🤖 Analyzing {len(text_content)} characters of {content_type} content with Gemini")
    
    # Create prompt based on content type
    if content_type == "resume":
        prompt = """
        Analyze this resume text and extract:
        1. Technical skills (programming languages, frameworks, tools, technologies)
        2. Soft skills and competencies
        3. Industry domains and areas of expertise
        4. Certifications and qualifications
        5. Key experience highlights
        
        Order each array with the strongest/most defining skills first and weaker/less identifiable ones later. Use evidence like frequency, recency, emphasis, and role impact when ranking.

        Format the response as JSON with these categories, keeping each array ordered strongest→weakest:
        - technical_skills: array of technical skills
        - soft_skills: array of soft skills
        - domains: array of industry domains/areas
        - certifications: array of certifications
        - experience_keywords: array of key experience terms
        
        Resume text:
        """
    elif content_type == "github":
        prompt = """
        Analyze these GitHub repository descriptions and README snippets to extract:
        1. Programming languages and technologies used
        2. Frameworks and libraries
        3. Project types and domains
        4. Development tools and methodologies
        5. Technical concepts and keywords
        
        Order each array with the strongest/most defining items first and weaker/less identifiable ones later. Use evidence like prominence in the README, code emphasis, and repo stars when ranking.

        Format the response as JSON with these categories, keeping each array ordered strongest→weakest:
        - languages: array of programming languages
        - frameworks: array of frameworks and libraries
        - tools: array of development tools
        - domains: array of project domains
        - concepts: array of technical concepts
        
        GitHub content:
        """
    else:  # mixed
        prompt = """
        Analyze this combined resume and GitHub content to extract:
        1. All technical skills (programming languages, frameworks, tools)
        2. Soft skills and competencies
        3. Project domains and industry areas
        4. Certifications and qualifications
        5. Key experience and project highlights
        
        Order each array with the strongest/most defining items first and weaker/less identifiable ones later. Use frequency, recency, prominence, and cross-source corroboration when ranking.

        Format the response as JSON with these categories, keeping each array ordered strongest→weakest:
        - technical_skills: array of all technical skills
        - soft_skills: array of soft skills
        - domains: array of domains and areas
        - certifications: array of certifications
        - keywords: array of other relevant keywords
        
        Content to analyze:
        """
    
    try:
        print("🤖 Creating Gemini model...")
        ModelCtor = getattr(genai, "GenerativeModel", None)
        if not callable(ModelCtor):
            raise RuntimeError("google.generativeai.GenerativeModel not available")
        model = ModelCtor('gemini-2.5-flash-lite')
        print("🤖 Model created successfully")
        
        gen_fn = getattr(model, "generate_content", None)
        if not callable(gen_fn):
            raise RuntimeError("generate_content not available on GenerativeModel instance")
        
        print("🤖 Sending request to Gemini...")
        response = gen_fn(prompt + text_content)
        print("🤖 Received response from Gemini")
        
        # Try to parse JSON response
        response_text = getattr(response, "text", None)
        if not isinstance(response_text, str):
            response_text = str(response)
        response_text = response_text.strip()
        
        print(f"🤖 Raw response length: {len(response_text)} characters")
        print(f"🤖 First 500 chars of response: {response_text[:500]}...")
        
        # Clean up the response if it's wrapped in markdown code blocks
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        
        print(f"🤖 Cleaned response length: {len(response_text)} characters")
        
        try:
            result = json.loads(response_text.strip())
            print(f"✅ Successfully parsed Gemini response for {content_type}")
            print(f"✅ Response keys: {list(result.keys())}")
            
            # Log array lengths for debugging
            for key, value in result.items():
                if isinstance(value, list):
                    print(f"✅ {key}: {len(value)} items")
                    if len(value) > 0:
                        print(f"   First few: {value[:3]}")
            
            return result
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse JSON from Gemini response for {content_type}: {e}")
            print(f"❌ Problematic text: {response_text[:1000]}...")
            # If JSON parsing fails, return a structured fallback
            return {
                "raw_response": response_text,
                "extraction_status": "failed_to_parse_json",
                "technical_skills": [],
                "soft_skills": [],
                "domains": [],
                "keywords": []
            }
            
    except Exception as e:
        print(f"❌ Error calling Gemini API for {content_type}: {e}")
        import traceback
        traceback.print_exc()
        return {
            "error": str(e),
            "extraction_status": "failed",
            "technical_skills": [],
            "soft_skills": [],
            "domains": [],
            "keywords": []
        }

def get_github_readmes(username: str, max_repos: int = 5) -> List[Dict]:
    """Wrapper function for GitHub scraping"""
    try:
        return summarize_user(username, max_repos)
    except Exception as e:
        print(f"❌ GitHub scraping failed: {e}")
        return []

def analyze_profile(github_username: Optional[str] = None, 
                   resume_path: Optional[str] = None,
                   max_repos: int = 5) -> Dict:
    """
    Main function to analyze a user's profile from GitHub and/or resume.
    
    Args:
        github_username: GitHub username to analyze
        resume_path: Path to resume file (PDF or image)
        max_repos: Maximum number of GitHub repos to analyze
        
    Returns:
        Dictionary containing all extracted information and skills
    """
    results = {
        "github_analysis": None,
        "resume_analysis": None,
        "combined_skills": None,
        "sources_used": []
    }
    
    combined_text = ""
    
    # Analyze GitHub profile
    if github_username:
        print(f"Starting GitHub analysis for: {github_username}")
        try:
            repos = get_github_readmes(github_username, max_repos)
            if repos:
                # Combine all README content
                github_text = ""
                for repo in repos:
                    github_text += f"\n--- {repo['repo_name']} by {repo['owner']} ---\n"
                    github_text += f"Description: {repo['description']}\n"
                    github_text += f"Primary Language: {repo['primary_language']}\n"
                    github_text += f"README: {repo['readme_snippet']}\n\n"
                
                print(f"Collected GitHub content: {len(github_text)} characters")
                results["github_analysis"] = extract_skills_with_gemini(github_text, "github")
                results["sources_used"].append("github")
                combined_text += github_text
            else:
                print("No GitHub repos with READMEs found")
                
        except Exception as e:
            print(f"Exception in GitHub analysis: {e}")
            results["github_analysis"] = {"error": str(e)}
    
    # Analyze resume
    if resume_path:
        print(f"Starting resume analysis for: {resume_path}")
        try:
            resume_text = extract_text_from_file(resume_path)
            if resume_text:
                print(f"Extracted resume text: {len(resume_text)} characters")
                results["resume_analysis"] = extract_skills_with_gemini(resume_text, "resume")
                results["sources_used"].append("resume")
                combined_text += f"\n--- RESUME CONTENT ---\n{resume_text}\n"
            else:
                print("No text extracted from resume")
                
        except Exception as e:
            print(f"Exception in resume analysis: {e}")
            results["resume_analysis"] = {"error": str(e)}
    
    # Combined analysis if we have content from both sources
    if len(results["sources_used"]) > 1 and combined_text:
        print("Running combined analysis")
        try:
            results["combined_skills"] = extract_skills_with_gemini(combined_text, "mixed")
        except Exception as e:
            print(f"Exception in combined analysis: {e}")
            results["combined_skills"] = {"error": str(e)}
    
    print(f"Analysis complete. Sources used: {results['sources_used']}")
    return results

def test_extraction(resume_path: str):
    """Test function to debug extraction issues"""
    print("🧪 Starting extraction test...")
    
    try:
        # Test text extraction
        text = extract_text_from_file(resume_path)
        print(f"✅ Text extraction successful: {len(text)} characters")
        
        if len(text) < 50:
            print("⚠️ Warning: Very short text extracted. May indicate extraction issues.")
            return
        
        # Test Gemini skills extraction
        skills = extract_skills_with_gemini(text, "resume")
        print(f"✅ Skills extraction result: {skills}")
        
        return skills
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

# CLI interface
def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Extract skills from GitHub profile and/or resume")
    parser.add_argument("--github", help="GitHub username to analyze")
    parser.add_argument("--resume", help="Path to resume file (PDF or image)")
    parser.add_argument("--output", help="Output JSON file path")
    parser.add_argument("--max-repos", type=int, default=5, help="Max GitHub repos to analyze")
    
    args = parser.parse_args()
    
    if not args.github and not args.resume:
        print("Error: Must provide either --github username or --resume file path")
        return 1
    
    results = analyze_profile(
        github_username=args.github,
        resume_path=args.resume,
        max_repos=args.max_repos
    )
    
    output_text = json.dumps(results, indent=2)
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_text)
        print(f"Results saved to {args.output}")
    else:
        print(output_text)
    
    return 0

if __name__ == "__main__":
    # Test mode - run extraction test on a specific file
    test_path = r"C:\Yash Dev\hackruf25\teamskills\.cache\resumes\Yash_Chennawar_1759673702499.pdf"
    if os.path.exists(test_path):
        test_extraction(test_path)
    else:
        print(f"Test file not found: {test_path}")
        print("You can also run the CLI with:")
        print("python skill_extractor.py --resume path/to/resume.pdf")