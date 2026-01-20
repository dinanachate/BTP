from .utils import context_from_query, call_llm, add_citation_links
import json
import re


class KnowledgeEnhancerAgent:
    """
    Agent 2: Enhances knowledge by identifying gaps and filling them.
    Asks clarifying questions and performs additional research.
    """
    
    def __init__(self, max_iterations=3, top_k=5):
        self.max_iterations = max_iterations
        self.top_k = top_k
        self.enhancement_sources = []
        
    def enhance_knowledge(self, subject, initial_knowledge, initial_sources):
        """Iteratively enhance knowledge by identifying and filling gaps."""
        print(f"\n🔬 Agent 2 : Amélioration des connaissances sur '{subject}'...")

        current_knowledge = initial_knowledge
        all_sources = initial_sources.copy()

        for iteration in range(self.max_iterations):
            print(f"   Itération {iteration + 1}/{self.max_iterations}")

            # Identify gaps
            gaps = self._identify_gaps(subject, current_knowledge)

            if not gaps or len(gaps) == 0:
                print("      ✓ Aucune lacune significative trouvée")
                break

            print(f"      → {len(gaps)} lacunes identifiées")

            # Fill gaps
            enhancements = self._fill_gaps(subject, gaps, all_sources)

            if not enhancements:
                print("      ✓ Aucune nouvelle information trouvée")
                break

            # Integrate enhancements
            current_knowledge = self._integrate_enhancements(
                subject, current_knowledge, enhancements, all_sources
            )

            print(f"      ✓ {len(self.enhancement_sources)} nouvelles sources ajoutées")
            all_sources.extend(self.enhancement_sources)
            self.enhancement_sources = []

        print(f"✅ Agent 2 : Connaissances enrichies avec {len(all_sources) - len(initial_sources)} sources supplémentaires")
        return current_knowledge, all_sources
    
    def _identify_gaps(self, subject, knowledge):
        """Identify gaps, unclear points, and missing information."""
        system_prompt = """You are an expert knowledge analyst.

IMPORTANT: You must respond in French.

Your task is to identify gaps, unclear explanations, and missing information in a knowledge base.
Look for:
- Important concepts that are mentioned but not explained
- Unclear or incomplete explanations
- Missing practical examples
- Lack of detail on key topics
- Questions a student might have that aren't answered"""

        user_prompt = f"""Subject: {subject}

<knowledge_base>
{knowledge}
</knowledge_base>

Analyze this knowledge base and identify gaps or areas that need more clarification.

Return ONLY a JSON array of specific questions/gaps, nothing else.
Each question should be specific and focused.
Limit to the 5 most important gaps.

Example format: ["Question about unclear concept X", "Need more detail on Y", "How does Z work in practice?"]"""

        response = call_llm(system_prompt, user_prompt)
        
        try:
            start = response.find('[')
            end = response.rfind(']') + 1
            gaps = json.loads(response[start:end])
            for gap in gaps:
                print(f"         • Lacune : {gap}")
            return gaps[:5]  # Limit to 5 most important
        except:
            return []
    
    def _fill_gaps(self, subject, gaps, existing_sources):
        """Fill identified gaps using RAG queries."""
        enhancements = []
        source_id_start = max([s['id'] for s in existing_sources]) + 1 if existing_sources else 1
        
        for gap in gaps:
            # Query RAG for this gap
            knowledge_base, sources = context_from_query(gap, top_k=self.top_k)
            
            # Re-number sources
            for source in sources:
                source['original_id'] = source['id']
                source['id'] = source_id_start
                source_id_start += 1
                self.enhancement_sources.append(source)
            
            enhancements.append({
                'gap': gap,
                'knowledge': knowledge_base,
                'sources': sources
            })
        
        return enhancements
    
    def _integrate_enhancements(self, subject, current_knowledge, enhancements, all_sources):
        """Integrate new knowledge into existing knowledge base."""
        system_prompt = """You are an expert knowledge integrator.

IMPORTANT: You must respond in French.

Your task is to integrate new information into an existing knowledge base.
- Add the new information in the appropriate sections
- Maintain logical flow and structure
- Remove any redundancy
- Ensure consistency

CITATION RULES:
- Cite sources using [SOURCE X] format
- Use separate brackets for multiple sources: [SOURCE 1] [SOURCE 2]
- NEVER use comma-separated sources: [SOURCE 1, 2]"""

        enhancement_text = []
        for enh in enhancements:
            enhancement_text.append(f"=== Gap: {enh['gap']} ===\n{enh['knowledge']}")
        
        user_prompt = f"""Subject: {subject}

<current_knowledge>
{current_knowledge}
</current_knowledge>

<new_information>
{chr(10).join(enhancement_text)}
</new_information>

Integrate the new information into the current knowledge base.
Add it to the appropriate sections, maintaining structure and flow.
Keep all existing citations and add new ones for the new information.

Return the complete updated knowledge base."""

        integrated = call_llm(system_prompt, user_prompt)
        
        # Add citation links
        integrated_with_links, _ = add_citation_links(integrated, all_sources + self.enhancement_sources)
        
        return integrated_with_links
