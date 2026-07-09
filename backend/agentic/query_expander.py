import json
import re
import sys
from backend.core.llm import complete as query_ollama

# Fix Unicode output on Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

def expand_query(user_query: str) -> list[str]:
    """Expands a search query into multiple queries for vector retrieval.
    
    Generates synonyms and translations (French/English) using Ollama.
    
    Args:
        user_query: The original raw string query.
        
    Returns:
        List of expanded string queries. Always includes the original query.
    """
    if not user_query or not user_query.strip():
        return []
    
    original_query = user_query.strip()
        
    system_prompt = (
        "You are an expert search engine query expander for a database of Terms of Reference (TDR) documents. "
        "Your task is to take a user's search query (which may be in French or English) and output alternative search "
        "queries to maximize search recall. "
        "Generate exactly 3 alternative queries:\n"
        "1. The original query cleaned of unnecessary words.\n"
        "2. Key synonyms or industry terms.\n"
        "3. A cross-lingual translation (e.g., if query is French, translate terms to English; if English, translate to French).\n\n"
        "You MUST respond ONLY with a valid JSON list of strings, for example: [\"query1\", \"query2\", \"query3\"]\n"
        "Do NOT include markdown blocks like ```json or any explanation. Output only the raw JSON array."
    )
    
    prompt = f"User query: '{original_query}'\n\nGenerate the JSON list of 3 search terms:"
    
    # Query LLM with temperature 0.1 (low randomness for consistent JSON)
    response = query_ollama(prompt, system_prompt=system_prompt, temperature=0.1)
    
    # Attempt to clean and parse JSON list
    try:
        clean_response = response.strip()
        
        # Remove markdown formatting if present
        if clean_response.startswith("```json"):
            clean_response = clean_response[7:]
        elif clean_response.startswith("```"):
            clean_response = clean_response[3:]
            
        if clean_response.endswith("```"):
            clean_response = clean_response[:-3]
        
        clean_response = clean_response.strip()
        
        # Try direct JSON parse first
        try:
            queries = json.loads(clean_response)
        except json.JSONDecodeError:
            # Fallback: extract first [...] block using regex
            match = re.search(r'\[.*?\]', clean_response, re.DOTALL)
            if not match:
                raise ValueError("No JSON array found in response")
            queries = json.loads(match.group(0))
        
        # Validate and clean results
        if isinstance(queries, list) and all(isinstance(q, str) for q in queries):
            # Remove duplicates while preserving order
            seen = set()
            result = []
            for q in queries:
                cleaned = q.strip()
                if cleaned and cleaned not in seen:
                    seen.add(cleaned)
                    result.append(cleaned)
            
            # Ensure original query is always included
            if original_query not in result:
                result.insert(0, original_query)
            
            return result
        else:
            raise ValueError(f"Invalid query list format: {queries}")
            
    except Exception as e:
        print(f"⚠️ Query expansion parser failed: {e}")
        if response:
            print(f"   Raw response: '{response[:100]}...'")
        
    # Fallback to original query only
    return [original_query]