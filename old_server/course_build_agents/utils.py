from retrivers.hybrid_retriever import retrieve
import os
import ollama
from ollama import Client
import re
import json
import sys
from pathlib import Path

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent))
from config_loader import settings

# Create Ollama client: cloud if key exists, local otherwise
if os.environ.get("OLLAMA_API_KEY"):
    ollama_client = Client(
        host="https://ollama.com",
        headers={"Authorization": f"Bearer {os.environ.get('OLLAMA_API_KEY')}"}
    )
    USE_CLOUD = True
else:
    ollama_client = ollama
    USE_CLOUD = False



def context_from_query(query, top_k=5):
    """Récupère le contexte pertinent avec métadonnées pour citation."""
    results = retrieve(query, top_k=top_k)
    
    knowledge_parts = []
    sources = []
    
    for i, result in enumerate(results, 1):
        source_url = result['metadata'].get('source_url', '')
        title = result['metadata'].get('title', 'Document sans titre')
        chunk_text = result['chunk_text']
        
        knowledge_parts.append(
            f"<knowledge id=\"{i}\" title=\"{title}\" url=\"{source_url}\">\n"
            f"{chunk_text}\n"
            f"</knowledge>"
        )
        
        sources.append({
            'id': i,
            'title': title,
            'url': source_url
        })
    
    knowledge_base = "\n\n".join(knowledge_parts)
    return knowledge_base, sources


def add_citation_links(text, sources):
    """Convertit [SOURCE X] en citations séquentielles [1](url), [2](url)..."""
    used_sources = re.findall(r'\[\s*SOURCE\s+(\d+)\s*\]', text)
    used_sources_unique = sorted(set(map(int, used_sources)))
    source_mapping = {old: new for new, old in enumerate(used_sources_unique, 1)}
    
    def replace_source(match):
        source_num = int(match.group(1))
        if source_num in source_mapping:
            sequential_num = source_mapping[source_num]
            source_url = next((s['url'] for s in sources if s['id'] == source_num), '#')
            return f'[{sequential_num}]({source_url})'
        return match.group(0)
    
    text = re.sub(r'\[\s*SOURCE\s+(\d+)\s*\]', replace_source, text)
    return text, source_mapping


def call_llm(system_prompt, user_prompt, model=None):
    """Wrapper pour appeler le LLM avec system et user prompts."""
    if model is None:
        model = settings.RAG_MODEL
    
    if USE_CLOUD:
        # Cloud: use chat() API
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        cloud_response = ollama_client.chat(
            model=model + "-cloud",
            messages=messages
        )
        return cloud_response['message']['content']
    else:
        # Local: use generate() API
        local_response = ollama_client.generate(
            model=model,
            prompt=user_prompt,
            system=system_prompt
        )
        return local_response['response']


def call_llm_structured_output(system_prompt, user_prompt,schema, model=None):
    """Wrapper pour appeler le LLM avec system et user prompts."""
    if model is None:
        model = settings.RAG_MODEL
    
    if USE_CLOUD:
        # Cloud: use chat() API
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        cloud_response = ollama_client.chat(
            model=model + "-cloud",
            messages=messages,
            format=schema
        )
        return cloud_response['message']['content']
    else:
        # Local: use generate() API
        local_response = ollama_client.generate(
            model=model,
            prompt=user_prompt,
            system=system_prompt
        )
        return local_response['response']

def fix_malformed_json(broken_json, expected_structure_description, error_message):
        """
        Failsafe function that asks LLM to fix malformed JSON.
        
        Args:
            broken_json: The string that failed to parse
            expected_structure_description: Description of what the JSON should look like
            error_message: The error message from json.loads()
        
        Returns:
            Corrected JSON string or None if correction fails
        """
        system_prompt = """You are a JSON repair specialist.

Your ONLY task is to fix malformed JSON and return valid, parsable JSON.

Common issues you fix:
- Missing or extra commas
- Unclosed brackets or braces
- Unescaped quotes in strings
- Trailing commas before closing brackets
- Missing quotes around keys
- Single quotes instead of double quotes
- Comments in JSON (which are invalid)

CRITICAL RULES:
1. Return ONLY valid JSON - nothing else
2. Do not add explanations or markdown
3. Do not wrap in code blocks
4. Preserve all content from the original
5. Only fix structural/syntax issues
6. Ensure proper encoding of special characters"""

        user_prompt = f"""The following JSON failed to parse with this error:
ERROR: {error_message}

BROKEN JSON:
{broken_json}

EXPECTED STRUCTURE:
{expected_structure_description}

Fix this JSON and return ONLY the corrected, valid JSON. No explanations, no markdown, just valid JSON."""

        try:
            corrected = call_llm(system_prompt, user_prompt)
            
            # Try to extract JSON if LLM wrapped it in markdown or text
            corrected = corrected.strip()
            
            # Remove markdown code blocks if present
            if corrected.startswith('```'):
                corrected = re.sub(r'^```(?:json)?\s*\n?', '', corrected)
                corrected = re.sub(r'\n?```\s*$', '', corrected)
            
            # Try to find JSON object
            start = corrected.find('{')
            end = corrected.rfind('}') + 1
            if start != -1 and end > start:
                corrected = corrected[start:end]
            
            # Validate it parses
            json.loads(corrected)
            print(f"   ✓ JSON successfully repaired by LLM")
            return corrected
            
        except Exception as repair_error:
            print(f"   ✗ Failed to repair JSON: {repair_error}")
            return None