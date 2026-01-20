from .utils import call_llm, fix_malformed_json
import json


class CourseGeneratorAgent:
    """
    Agent 3: Generates comprehensive course structure.
    Creates chapters, subchapters, and detailed content outlines for teaching.
    """
    
    def __init__(self):
        self.course_structure = None
        
    def generate_course(self, subject, knowledge_base, sources):
        """Generate a complete course structure from the knowledge base."""
        print(f"\n📚 Agent 3 : Génération de la structure du cours sur '{subject}'...")

        # Step 1: Generate course outline
        print(f"   Étape 1 : Création du plan général du cours...")
        outline = self._generate_outline(subject, knowledge_base)
        print(f"      ✓ Plan créé avec {len(outline.get('chapters', []))} chapitres")

        # Step 2: Generate detailed chapter content
        print(f"   Étape 2 : Détail de chaque chapitre...")
        detailed_structure = self._generate_detailed_structure(subject, knowledge_base, outline)

        print(f"✅ Agent 3 : Structure du cours générée avec succès")

        self.course_structure = detailed_structure
        return detailed_structure
    
    def _generate_outline(self, subject, knowledge_base):
        """Generate high-level course outline."""
        system_prompt = """You are an expert curriculum designer.

IMPORTANT: You must respond in French.

Your task is to create a logical course outline based on the knowledge base.
Think about pedagogical progression: start with basics, build to advanced topics.

Consider:
- Prerequisites and foundational concepts first
- Logical progression of difficulty
- Balance between theory and practice
- Student learning journey"""

        user_prompt = f"""Subject: {subject}

<knowledge_base>
{knowledge_base}
</knowledge_base>

Create a course outline with 5-10 chapters that will teach this subject effectively to students.

IMPORTANT: the course must contain at least 5 chapters.

Return ONLY a JSON object with this structure:
{{
  "course_title": "Title in French",
  "description": "Brief course description",
  "target_audience": "Who this course is for",
  "chapters": [
    {{"chapter_number": 1, "title": "Chapter title", "description": "What this chapter covers"}},
    ...
  ]
}}"""

        response = call_llm(system_prompt, user_prompt)
        
        try:
            start = response.find('{')
            end = response.rfind('}') + 1
            outline = json.loads(response[start:end])
            return outline
        except Exception as e:
            print(f"   Warning: Could not parse outline JSON: {e}")
            print("    trying to fix malformed JSON...")
            fixed_json = fix_malformed_json(response, """{
  "course_title": "Title in French",
  "description": "Brief course description",
  "target_audience": "Who this course is for",
  "chapters": [
    {"chapter_number": 1, "title": "Chapter title", "description": "What this chapter covers"},
    ...
  ]
}""", str(e))
            if fixed_json:
                try:
                    outline = json.loads(fixed_json)
                    return outline
                except Exception as e2:
                    print(f"   Warning: Could not parse fixed JSON: {e2}")
            print("   Returning minimal course structure")  
            # Return minimal structure
            return {
                "course_title": f"Course sur {subject}",
                "description": "Course description",
                "target_audience": "Students",
                "chapters": [{"chapter_number": 1, "title": "Introduction", "description": "Introduction"}]
            }
    
    def _generate_detailed_structure(self, subject, knowledge_base, outline):
        """Generate detailed structure for each chapter with subchapters and content."""
        system_prompt = """You are an expert curriculum designer.

IMPORTANT: You must respond in French.

Your task is to create detailed chapter structures with subchapters and specific content to teach.

For each chapter:
- Break it into 3-6 logical subchapters
- For each subchapter, specify exactly what concepts, principles, or skills to teach
- Include learning objectives
- Note practical examples or exercises to include
- Suggest estimated duration"""

        detailed_chapters = []

        for chapter in outline.get('chapters', []):
            print(f"      → Chapitre {chapter['chapter_number']} : {chapter['title']}")

            user_prompt = f"""Subject: {subject}

<knowledge_base>
{knowledge_base}
</knowledge_base>

Chapter {chapter['chapter_number']}: {chapter['title']}
Description: {chapter['description']}

Create a detailed structure for this chapter.

Return ONLY a JSON object with this structure:
{{
  "chapter_number": {chapter['chapter_number']},
  "title": "{chapter['title']}",
  "description": "{chapter['description']}",
  "learning_objectives": ["objective 1", "objective 2", ...],
  "estimated_duration": "Duration estimate (e.g., 2 hours)",
  "subchapters": [
    {{
      "subchapter_number": "1.1",
      "title": "Subchapter title",
      "content_to_cover": [
        "Specific concept or skill to teach",
        "Another concept to cover",
        ...
      ],
      "practical_elements": ["Example 1", "Exercise 1", ...],
      "estimated_duration": "30 minutes"
    }},
    ...
  ]
}}"""

            response = call_llm(system_prompt, user_prompt)
            
            try:
                start = response.find('{')
                end = response.rfind('}') + 1
                chapter_detail = json.loads(response[start:end])
                detailed_chapters.append(chapter_detail)
                print(f"         ✓ {len(chapter_detail.get('subchapters', []))} sous-chapitres créés")
            except Exception as e:
                print(f"         ⚠ Erreur lors de l'analyse du chapitre {chapter['chapter_number']}: {e}")
                print(f"         → Tentative de correction du JSON...")
                fixed_json = fix_malformed_json(response, """{{
  "chapter_number": {chapter['chapter_number']},
  "title": "{chapter['title']}",
  "description": "{chapter['description']}",
  "learning_objectives": ["objective 1", "objective 2", ...],
  "estimated_duration": "Duration estimate (e.g., 2 hours)",
  "subchapters": [
    {{
      "subchapter_number": "1.1",
      "title": "Subchapter title",
      "content_to_cover": [
        "Specific concept or skill to teach",
        "Another concept to cover",
        ...
      ],
      "practical_elements": ["Example 1", "Exercise 1", ...],
      "estimated_duration": "30 minutes"
    }},
    ...
  ]
}}""", str(e))
                if fixed_json:
                    try:
                        chapter_detail = json.loads(fixed_json)
                        detailed_chapters.append(chapter_detail)
                        print(f"         ✓ {len(chapter_detail.get('subchapters', []))} sous-chapitres créés (après correction)")
                        continue
                    except Exception as e2:
                        print(f"         ✗ Impossible de corriger le JSON pour le chapitre {chapter['chapter_number']}")
                        # Add minimal structure
                        detailed_chapters.append({
                            "chapter_number": chapter['chapter_number'],
                            "title": chapter['title'],
                            "description": chapter['description'],
                            "subchapters": []
                        })
        
        # Assemble complete course structure
        complete_structure = {
            "course_title": outline.get('course_title', f"Course sur {subject}"),
            "description": outline.get('description', ''),
            "target_audience": outline.get('target_audience', ''),
            "total_chapters": len(detailed_chapters),
            "chapters": detailed_chapters
        }
        
        return complete_structure
    
    def get_markdown_content(self):
        """Generate markdown content as a string without saving to file."""
        if not self.course_structure:
            return "Aucune structure de cours disponible."

        md_content = []

        # Header
        md_content.append(f"# {self.course_structure['course_title']}\n")
        md_content.append(f"**Description:** {self.course_structure['description']}\n")
        md_content.append(f"**Public cible:** {self.course_structure['target_audience']}\n")
        md_content.append(f"**Nombre de chapitres:** {self.course_structure['total_chapters']}\n")
        md_content.append("---\n")

        # Chapters
        for ch_idx , chapter in enumerate(self.course_structure['chapters']):
            md_content.append(f"\n## Chapitre {ch_idx + 1}: {chapter['title']}\n")
            md_content.append(f"{chapter['description']}\n")

            if 'learning_objectives' in chapter:
                md_content.append(f"\n**Objectifs d'apprentissage:**")
                for obj in chapter['learning_objectives']:
                    md_content.append(f"- {obj}")
                md_content.append("")

            #if 'estimated_duration' in chapter:
            #    md_content.append(f"**Durée estimée:** {chapter['estimated_duration']}\n")

            # Subchapters
            if 'subchapters' in chapter:
                for sub_idx, subchapter in enumerate(chapter['subchapters']):
                    md_content.append(f"\n### {ch_idx + 1}.{sub_idx + 1} - {subchapter['title']}\n")

                    #if 'estimated_duration' in subchapter:
                    #    md_content.append(f"*Durée: {subchapter['estimated_duration']}*\n")

                    if 'content_to_cover' in subchapter:
                        md_content.append("**Contenu à couvrir:**")
                        for content in subchapter['content_to_cover']:
                            md_content.append(f"- {content}")
                        md_content.append("")

                    if 'practical_elements' in subchapter:
                        md_content.append("**Éléments pratiques:**")
                        for element in subchapter['practical_elements']:
                            md_content.append(f"- {element}")
                        md_content.append("")

            md_content.append("---")

        return '\n'.join(md_content)

    def export_to_markdown(self, output_path):
        """Export course structure to a readable markdown file."""
        if not self.course_structure:
            print("No course structure to export")
            return

        md_content = self.get_markdown_content()

        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md_content)

        print(f"   Course structure exported to: {output_path}")
