import json
import os
import tempfile
from typing import List, Dict, Optional, Union
import google.generativeai as genai
from dotenv import load_dotenv

from .github_scraper import summarize_user
from .resume_scraper import extract_with_pdfplumber, extract_with_gcv

# Load environment variables - check multiple locations
load_dotenv()  # Default behavior
# Also try loading from parent directory
parent_dir = os.path.dirname(os.path.dirname(__file__))
env_local_path = os.path.join(parent_dir, '.env.local')
if os.path.exists(env_local_path):
    load_dotenv(env_local_path)

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    try:
        configure_fn = getattr(genai, "configure", None)
        if callable(configure_fn):
            configure_fn(api_key=GEMINI_API_KEY)
    except Exception as _e:
        print(f"Warning: failed to configure Gemini: {_e}")

def extract_text_from_file(file_path: str, threshold: int = 500) -> str:
    """
    Extract text from a resume file (PDF or image) using the resume_scraper logic.
    
    Args:
        file_path: Path to the resume file
        threshold: Minimum text length before falling back to OCR
        
    Returns:
        Extracted text content
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    ext = os.path.splitext(file_path)[1].lower()
    extracted = ""
    
    try:
        if ext == ".pdf":
            # Try pdfplumber first
            extracted = extract_with_pdfplumber(file_path)
            
            # Fall back to Vision OCR if text is too short
            if len(extracted) < threshold:
                gcv_text = extract_with_gcv(file_path)
                if len(gcv_text) > len(extracted):
                    extracted = gcv_text
        else:
            # For images, use Vision OCR directly
            extracted = extract_with_gcv(file_path)
            
    except Exception as e:
        # Last resort: try Vision OCR
        try:
            extracted = extract_with_gcv(file_path)
        except Exception as e2:
            raise RuntimeError(f"Failed to extract text: {e}. Vision fallback error: {e2}")
    
    return extracted

def get_github_readmes(username: str, max_repos: int = 5) -> List[Dict]:
    """
    Get README content from top GitHub repositories for a user.
    
    Args:
        username: GitHub username
        max_repos: Maximum number of repositories to analyze
        
    Returns:
        List of dictionaries containing repo info and README snippets
    """
    try:
        print(f"Fetching GitHub data for user: {username}")
        summary = summarize_user(username)
        print(f"GitHub summary keys: {list(summary.keys()) if summary else 'None'}")
        
        if not summary:
            print("No summary returned from GitHub scraper")
            return []
        
        # Check if user was found (the github_scraper might return an error structure)
        if "error" in summary or summary.get("username") != username:
            print(f"User not found or error in summary: {summary}")
            return []
        
        # Get top repos with README content
        repos_with_readmes = []
        repos = summary.get("top_repos", [])
        print(f"Found {len(repos)} top repos")
        
        for i, repo in enumerate(repos[:max_repos]):
            print(f"Processing repo {i+1}: {repo.get('repo')} - README present: {bool(repo.get('readme_snippet'))}")
            if repo.get("readme_snippet"):
                repos_with_readmes.append({
                    "repo_name": repo.get("repo"),
                    "owner": repo.get("owner"),
                    "description": repo.get("description", ""),
                    "primary_language": repo.get("primary_language"),
                    "stars": repo.get("stars", 0),
                    "readme_snippet": repo.get("readme_snippet")
                })
        
        print(f"Collected {len(repos_with_readmes)} repos with READMEs")
        return repos_with_readmes
        
    except Exception as e:
        print(f"Error fetching GitHub data for {username}: {e}")
        import traceback
        traceback.print_exc()
        return []

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
    
    print(f"Analyzing {len(text_content)} characters of {content_type} content with Gemini")
    
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
        ModelCtor = getattr(genai, "GenerativeModel", None)
        if not callable(ModelCtor):
            raise RuntimeError("google.generativeai.GenerativeModel not available")
        model = ModelCtor('gemini-2.5-flash-lite')
        gen_fn = getattr(model, "generate_content", None)
        if not callable(gen_fn):
            raise RuntimeError("generate_content not available on GenerativeModel instance")
        response = gen_fn(prompt + text_content)
        
        # Try to parse JSON response
        response_text = getattr(response, "text", None)
        if not isinstance(response_text, str):
            response_text = str(response)
        response_text = response_text.strip()
        
        # Clean up the response if it's wrapped in markdown code blocks
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        
        try:
            result = json.loads(response_text.strip())
            print(f"Successfully parsed Gemini response for {content_type}")
            return result
        except json.JSONDecodeError:
            print(f"Failed to parse JSON from Gemini response for {content_type}")
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
        print(f"Error calling Gemini API for {content_type}: {e}")
        return {
            "error": str(e),
            "extraction_status": "failed",
            "technical_skills": [],
            "soft_skills": [],
            "domains": [],
            "keywords": []
        }

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
    exit(main())