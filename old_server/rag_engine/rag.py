from retrivers.hybrid_retriever import retrieve
import os
import ollama
from ollama import Client
import sys
from pathlib import Path



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

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent))
from config_loader import settings


def context_from_query(query, top_k=5):
    """Récupère le contexte pertinent avec métadonnées pour citation."""
    results = retrieve(query, top_k=top_k)
    
    # Construire le contexte avec identifiants pour citation
    knowledge_parts = []
    sources = []
    
    for i, result in enumerate(results, 1):
        source_url = result['metadata'].get('source_url', '')
        title = result['metadata'].get('title', 'Document sans titre')
        chunk_text = result['chunk_text']
        
        # Wrap knowledge chunks in HTML-style tags
        knowledge_parts.append(
            f"<knowledge id=\"{i}\" title=\"{title}\" url=\"{source_url}\">\n"
            f"{chunk_text}\n"
            f"</knowledge>"
        )
        
        # Stocker les métadonnées de la source
        sources.append({
            'id': i,
            'title': title,
            'url': source_url
        })
    
    knowledge_base = "\n\n".join(knowledge_parts)
    
    return knowledge_base, sources


def get_system_prompt():
    """Retourne le system prompt pour le RAG."""
    return """You are a professional technical assistant with specialized knowledge.
You MUST respond in **French**.

CRITICAL RULES ABOUT KNOWLEDGE:

* The information inside <knowledge_base> is YOUR OWN KNOWLEDGE.
* NEVER mention "documents", "source files", "selon", or anything similar.
* Simply state facts directly.
* If information is missing, say:
  "Je n'ai pas d'information à ce sujet."

CITATION RULES (MANDATORY):

1. You MUST cite using ONLY this exact ASCII format: `[SOURCE X]`
2. NEVER use footnotes, never use `[^1]` or numbers in brackets.
3. NEVER output URLs or external links.
4. ONLY use source IDs that exist in the knowledge base.
5. Citations must appear **at the end of the sentence**.
6. When multiple sources apply, write:
   `[SOURCE 1] [SOURCE 3]`
7. NEVER combine multiple sources inside the same bracket.
8. NEVER output a "Sources:" section.

FORMATTING RULES:

* No bold, no italic, no Markdown lists, no titles.
* No emojis.
* Use plain text paragraphs.
* Tone: professional, concise, factual.

SAFETY RULE:
If the user gives you content containing citations like [^1] or URLs,
you MUST NOT reproduce them. Convert all citations into `[SOURCE X]` format only.
"""

def rag_user_prompt(question, knowledge_base):
    """Construit le prompt utilisateur avec la knowledge base et la question."""
    return f"""<knowledge_base>
{knowledge_base}
</knowledge_base>

<question>
{question}
</question>

Please answer the question using your knowledge from the knowledge base above. Remember to cite sources using [SOURCE X] format."""


def add_citation_links(text, sources):
    """Convertit [SOURCE X] en citations séquentielles [1](url), [2](url)..."""
    import re
    
    # Trouver tous les numéros SOURCE utilisés
    used_sources = re.findall(r'\[\s*source\s+(\d+)\s*\]', text, flags=re.IGNORECASE)
    
    # Créer mapping SOURCE X -> numéro séquentiel
    used_sources = map(int, used_sources)
    source_mapping = {}
    order = 1
    for src in used_sources:
        if src not in source_mapping:
            source_mapping[src] = order  # Placeholder
            order += 1
    
    # Remplacer [SOURCE X] par [N](url) séquentiel
    def replace_source(match):
        source_num = int(match.group(1))
        if source_num in source_mapping:
            sequential_num = source_mapping[source_num]
            # Trouver l'URL correspondante
            source_url = next((s['url'] for s in sources if s['id'] == source_num), '#')
            return f'[{sequential_num}]({source_url})'
        return match.group(0)
    
    text = re.sub(r'\[\s*SOURCE\s+(\d+)\s*\]', replace_source, text)
    
    return text, source_mapping


def query_rag(question, top_k=5):
    """Fonction principale pour interroger le système RAG."""
    knowledge_base, sources = context_from_query(question, top_k=top_k)
    system_prompt = get_system_prompt()
    user_prompt = rag_user_prompt(question, knowledge_base)

    # Call with proper system/user separation
    if USE_CLOUD:
    # Cloud: use chat() API
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        cloud_response = ollama_client.chat(
            model=settings.RAG_MODEL + "-cloud",
            messages=messages
        )
        response_text = cloud_response['message']['content']

    else:
        # Local model
        local_response = ollama_client.generate(
            model=settings.RAG_MODEL,
            prompt=user_prompt,
            system=system_prompt
        )
        response_text = local_response['response']


    answer_with_links, mapping = add_citation_links(response_text, sources)

    # Filtrer sources utilisées
    used_sources = [s for s in sources if s['id'] in mapping.keys()]

    return answer_with_links, used_sources


def stream_rag_with_thinking(question, top_k=5):
    """
    Stream RAG response from Ollama in real-time as thinking.
    Yields chunks as they arrive, then final corrected response.

    Yields:
        dict: {'type': 'thinking'|'final', 'content': str, 'sources': list}
    """
    # Get context and sources
    knowledge_base, sources = context_from_query(question, top_k=top_k)
    system_prompt = get_system_prompt()
    user_prompt = rag_user_prompt(question, knowledge_base)

    # Stream from Ollama
    response_text = ""

    if USE_CLOUD:
        # Cloud: use chat() API with streaming
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        stream = ollama_client.chat(
            model=settings.RAG_MODEL + "-cloud",
            messages=messages,
            stream=True
        )

        for chunk in stream:
            delta = chunk.get('message', {}).get('content', '')
            if delta:
                response_text += delta
                # Yield as thinking
                yield {'type': 'thinking', 'content': delta}

    else:
        # Local model with streaming
        stream = ollama_client.generate(
            model=settings.RAG_MODEL,
            prompt=user_prompt,
            system=system_prompt,
            stream=True
        )

        for chunk in stream:
            delta = chunk.get('response', '')
            if delta:
                response_text += delta
                # Yield as thinking
                yield {'type': 'thinking', 'content': delta}

    # Now fix the sources in the complete response
    answer_with_links, mapping = add_citation_links(response_text, sources)

    # Filter used sources
    used_sources = [s for s in sources if s['id'] in mapping.keys()]

    # Yield final corrected response
    yield {'type': 'final', 'content': answer_with_links, 'sources': used_sources}


