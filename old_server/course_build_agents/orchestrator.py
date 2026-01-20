from course_build_agents.knowledge_retriever import KnowledgeRetrieverAgent
from course_build_agents.knowledge_enhancer import KnowledgeEnhancerAgent
from course_build_agents.course_generator import CourseGeneratorAgent
import json
import os
from datetime import datetime


class MultiAgentOrchestrator:
    """
    Orchestrates the three-agent system for course generation.
    
    Flow:
    1. Knowledge Retriever: Gathers comprehensive knowledge
    2. Knowledge Enhancer: Identifies gaps and improves quality
    3. Course Generator: Creates structured course from knowledge
    """
    
    def __init__(self, config=None):
        """
        Initialize orchestrator with optional configuration.
        
        config example:
        {
            'retriever_top_k': 5,
            'enhancer_iterations': 3,
            'enhancer_top_k': 5,
            'output_dir': './output'
        }
        """
        config = config or {}
        
        self.retriever = KnowledgeRetrieverAgent(
            top_k_per_query=config.get('retriever_top_k', 5)
        )
        self.enhancer = KnowledgeEnhancerAgent(
            max_iterations=config.get('enhancer_iterations', 3),
            top_k=config.get('enhancer_top_k', 5)
        )
        self.course_generator = CourseGeneratorAgent()
        
        self.output_dir = config.get('output_dir', './output')
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.results = {}
        
    def run(self, subject):
        """
        Execute the complete multi-agent workflow.
        
        Args:
            subject: The topic to create a course about
            
        Returns:
            dict: Complete results including knowledge base and course structure
        """
        print("=" * 80)
        print(f"MULTI-AGENT COURSE GENERATION SYSTEM")
        print(f"Subject: {subject}")
        print("=" * 80)
        
        start_time = datetime.now()
        
        # AGENT 1: Knowledge Retrieval
        print("\n" + "=" * 80)
        knowledge_base, sources = self.retriever.retrieve_knowledge(subject)
        
        self.results['initial_knowledge'] = knowledge_base
        self.results['initial_sources'] = sources
        self.results['initial_source_count'] = len(sources)
        
        # Save initial knowledge
        self._save_knowledge(knowledge_base, sources, 'initial_knowledge.md')
        
        # AGENT 2: Knowledge Enhancement
        print("\n" + "=" * 80)
        enhanced_knowledge, all_sources = self.enhancer.enhance_knowledge(
            subject, knowledge_base, sources
        )
        
        self.results['enhanced_knowledge'] = enhanced_knowledge
        self.results['all_sources'] = all_sources
        self.results['final_source_count'] = len(all_sources)
        self.results['sources_added'] = len(all_sources) - len(sources)
        
        # Save enhanced knowledge
        self._save_knowledge(enhanced_knowledge, all_sources, 'enhanced_knowledge.md')
        
        # AGENT 3: Course Generation
        print("\n" + "=" * 80)
        course_structure = self.course_generator.generate_course(
            subject, enhanced_knowledge, all_sources
        )
        
        self.results['course_structure'] = course_structure
        
        # Save course structure
        course_path = os.path.join(self.output_dir, 'course_structure.md')
        self.course_generator.export_to_markdown(course_path)
        
        # Save complete results as JSON
        self._save_json_results()
        
        # Summary
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print("\n" + "=" * 80)
        print("PROCESS COMPLETED")
        print("=" * 80)
        print(f"Subject: {subject}")
        print(f"Initial sources: {self.results['initial_source_count']}")
        print(f"Sources added by enhancer: {self.results['sources_added']}")
        print(f"Total sources: {self.results['final_source_count']}")
        print(f"Total chapters: {course_structure.get('total_chapters', 0)}")
        print(f"Duration: {duration:.2f} seconds")
        print(f"\nOutput directory: {self.output_dir}")
        print("=" * 80)
        
        return self.results
    
    def _save_knowledge(self, knowledge, sources, filename):
        """Save knowledge base with sources to markdown file."""
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"# Knowledge Base\n\n")
            f.write(knowledge)
            f.write("\n\n---\n\n")
            f.write("## Sources\n\n")
            for i, source in enumerate(sources, 1):
                f.write(f"{i}. [{source['title']}]({source['url']})\n")
        
        print(f"   Saved: {filepath}")
    
    def _save_json_results(self):
        """Save complete results as JSON for programmatic access."""
        filepath = os.path.join(self.output_dir, 'results.json')
        
        # Create simplified version (without full text for readability)
        json_results = {
            'initial_source_count': self.results['initial_source_count'],
            'final_source_count': self.results['final_source_count'],
            'sources_added': self.results['sources_added'],
            'course_structure': self.results['course_structure'],
            'sources': [
                {
                    'id': s['id'],
                    'title': s['title'],
                    'url': s['url']
                }
                for s in self.results['all_sources']
            ]
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(json_results, f, ensure_ascii=False, indent=2)
        
        print(f"   Saved: {filepath}")


def main():
    """Example usage of the multi-agent system."""
    
    # Configuration
    config = {
        'retriever_top_k': 5,          # Number of sources per query in retrieval
        'enhancer_iterations': 3,       # Max iterations for knowledge enhancement
        'enhancer_top_k': 5,            # Sources per gap-filling query
        'output_dir': './course_output'
    }
    
    # Initialize orchestrator
    orchestrator = MultiAgentOrchestrator(config)
    
    # Run the system
    subject = "Machine Learning"  # Change this to your subject
    results = orchestrator.run(subject)
    
    print("\n✅ Course generation complete!")
    print(f"📁 Check the output in: {config['output_dir']}/")


if __name__ == "__main__":
    main()
