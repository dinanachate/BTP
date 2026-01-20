from .utils import context_from_query, call_llm, add_citation_links
import json


class KnowledgeRetrieverAgent:
    """
    Agent 1: Retrieves comprehensive knowledge on a subject.
    Generates multiple queries to cover all aspects of the topic.
    """
    
    def __init__(self, top_k_per_query=5):
        self.top_k_per_query = top_k_per_query
        self.all_sources = []
        
    def generate_search_queries(self, subject):
        """Generate multiple search queries to cover the subject comprehensively."""
        system_prompt = """You are an expert research assistant.
Your task is to generate comprehensive search queries to gather all relevant knowledge about a subject.

IMPORTANT: You must respond in French."""

        user_prompt = f"""Subject: {subject}

Generate 8-10 diverse search queries that will help retrieve comprehensive knowledge about this subject.
The queries should cover:
- Core concepts and definitions
- Historical context and evolution
- Key principles and mechanisms
- Practical applications
- Advanced topics
- Common challenges and solutions
- Related technologies or methods
- Best practices

Return ONLY a JSON array of query strings, nothing else.
Example format: ["query 1", "query 2", "query 3"]"""

        response = call_llm(system_prompt, user_prompt)
        
        # Extract JSON from response
        try:
            start = response.find('[')
            end = response.rfind(']') + 1
            queries = json.loads(response[start:end])
            return queries
        except:
            # Fallback: basic queries
            return [
                subject,
                f"{subject} concepts fondamentaux",
                f"{subject} principes",
                f"{subject} applications pratiques",
                f"{subject} techniques avancées"
            ]
    
    def retrieve_knowledge(self, subject):
        """Retrieve and structure knowledge from multiple queries."""
        print(f"📚 Agent 1 : Collecte des connaissances sur '{subject}'...")

        # Generate diverse queries
        queries = self.generate_search_queries(subject)
        print(f"   {len(queries)} requêtes de recherche générées")

        # Retrieve knowledge for each query
        all_knowledge = []
        source_id_counter = 1

        for idx, query in enumerate(queries, 1):
            print(f"   Requête {idx}/{len(queries)} : {query[:60]}...")
            knowledge_base, sources = context_from_query(query, top_k=self.top_k_per_query)

            # Re-number sources to avoid conflicts
            for source in sources:
                source['original_id'] = source['id']
                source['id'] = source_id_counter
                source_id_counter += 1
                self.all_sources.append(source)

            print(f"      ✓ {len(sources)} sources trouvées")

            all_knowledge.append({
                'query': query,
                'knowledge': knowledge_base,
                'sources': sources
            })

        # Synthesize all knowledge
        synthesized = self._synthesize_knowledge(subject, all_knowledge)

        print(f"✅ Agent 1 : Connaissances récupérées depuis {len(self.all_sources)} sources")
        return synthesized, self.all_sources
    
    def _synthesize_knowledge(self, subject, all_knowledge):
        """Synthesize retrieved knowledge into structured format."""
        system_prompt = """You are an expert knowledge synthesizer.

IMPORTANT: You must respond in French.

Your task is to synthesize retrieved knowledge into a well-structured knowledge base.
Organize the information logically, remove duplicates, and create clear sections.

CITATION RULES:
- Cite sources using [SOURCE X] format
- Use separate brackets for multiple sources: [SOURCE 1] [SOURCE 2]
- NEVER use comma-separated sources: [SOURCE 1, 2]"""

        # Build comprehensive knowledge base
        knowledge_sections = []
        for idx, kb in enumerate(all_knowledge, 1):
            knowledge_sections.append(f"=== Search Query {idx}: {kb['query']} ===\n{kb['knowledge']}")
        
        user_prompt = f"""Subject: {subject}

<knowledge_base>
{chr(10).join(knowledge_sections)}
</knowledge_base>

Synthesize this knowledge into a comprehensive, well-organized knowledge base about {subject}.

Structure your response as:
1. Overview and definition
2. Core concepts
3. Key principles and mechanisms
4. Applications and use cases
5. Advanced topics
6. Best practices and considerations

Be thorough and cite all sources appropriately using [SOURCE X] format."""

        synthesized = call_llm(system_prompt, user_prompt)
        
        # Add citation links
        synthesized_with_links, _ = add_citation_links(synthesized, self.all_sources)
        
        return synthesized_with_links
