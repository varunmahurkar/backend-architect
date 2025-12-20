from typing import Dict, Optional
from pathlib import Path
import json


class PromptManager:
    """Manages prompt templates for LLM interactions."""

    def __init__(self, prompts_dir: Optional[Path] = None):
        """Initialize the prompt manager.

        Args:
            prompts_dir: Directory containing prompt template files
        """
        if prompts_dir is None:
            prompts_dir = Path(__file__).parent / "templates"

        self.prompts_dir = prompts_dir
        self._prompts_cache: Dict[str, str] = {}
        self._load_default_prompts()

    def _load_default_prompts(self):
        """Load default prompt templates into cache."""
        self._prompts_cache = {
            "general_qa": """You are a helpful AI assistant. Answer the following question accurately and concisely.

Question: {question}

Answer:""",

            "detailed_explanation": """You are an expert AI assistant. Provide a detailed and comprehensive explanation for the following question.

Question: {question}

Please structure your response with:
1. A brief overview
2. Detailed explanation
3. Key points or examples
4. Conclusion or summary

Response:""",

            "code_assistant": """You are an expert programming assistant. Help with the following coding question or task.

Task: {question}

Provide:
1. Clear explanation of the solution
2. Well-commented code
3. Usage examples if applicable

Response:""",

            "summarization": """You are a professional summarizer. Summarize the following content concisely while maintaining key information.

Content: {content}

Summary:""",

            "creative_writing": """You are a creative writing assistant. Help with the following creative writing task.

Prompt: {question}

Response:""",

            "data_analysis": """You are a data analysis expert. Analyze the following data or question.

Question: {question}

Provide:
1. Analysis approach
2. Key findings
3. Insights and recommendations

Response:""",
        }

    def get_prompt(self, prompt_name: str, **kwargs) -> str:
        """Get a prompt template and format it with provided arguments.

        Args:
            prompt_name: Name of the prompt template
            **kwargs: Variables to format the prompt with

        Returns:
            Formatted prompt string

        Raises:
            KeyError: If prompt template not found
        """
        # Try to load from file if not in cache
        if prompt_name not in self._prompts_cache:
            self._load_prompt_from_file(prompt_name)

        template = self._prompts_cache.get(prompt_name)
        if template is None:
            raise KeyError(f"Prompt template '{prompt_name}' not found")

        return template.format(**kwargs)

    def _load_prompt_from_file(self, prompt_name: str):
        """Load a prompt template from file.

        Args:
            prompt_name: Name of the prompt template file (without extension)
        """
        prompt_file = self.prompts_dir / f"{prompt_name}.txt"

        if prompt_file.exists():
            with open(prompt_file, 'r', encoding='utf-8') as f:
                self._prompts_cache[prompt_name] = f.read()

    def add_prompt(self, prompt_name: str, template: str, save_to_file: bool = False):
        """Add a new prompt template.

        Args:
            prompt_name: Name for the prompt template
            template: The prompt template string
            save_to_file: Whether to save the template to a file
        """
        self._prompts_cache[prompt_name] = template

        if save_to_file:
            self.prompts_dir.mkdir(parents=True, exist_ok=True)
            prompt_file = self.prompts_dir / f"{prompt_name}.txt"
            with open(prompt_file, 'w', encoding='utf-8') as f:
                f.write(template)

    def list_prompts(self) -> list:
        """List all available prompt templates.

        Returns:
            List of prompt template names
        """
        return list(self._prompts_cache.keys())

    def get_prompt_info(self) -> Dict[str, str]:
        """Get information about all available prompts.

        Returns:
            Dictionary mapping prompt names to their templates
        """
        return self._prompts_cache.copy()


# Global prompt manager instance
prompt_manager = PromptManager()
