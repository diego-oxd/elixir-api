#!/usr/bin/env python3
"""
Standalone script to generate documentation for a codebase using Claude Agent SDK.

This script mirrors the functionality of the /code-query/generate-docs endpoint
but can be run directly from the command line.

Usage:
    python scripts/generate_documentation.py <repo_path> <prompt_name>

Examples:
    python scripts/generate_documentation.py /path/to/repo api
    python scripts/generate_documentation.py /path/to/repo frontend
    python scripts/generate_documentation.py /path/to/repo project_overview
    python scripts/generate_documentation.py /path/to/repo data_model

Available prompts:
    - api: API endpoints documentation (JSON output)
    - data_model: Data model structure documentation (JSON output)
    - project_overview: High-level project overview (Markdown output)
    - frontend: Frontend components and structure (Markdown output)

Outputs are saved to:
    - Markdown prompts: scripts/outputs/<prompt_name>_<timestamp>.md
    - JSON prompts: scripts/outputs/<prompt_name>_<timestamp>.json
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Add project root to Python path so we can import from app/
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.agent import query_codebase_json, query_codebase_markdown
from app.services.prompts import prompts


def save_markdown_output(prompt_name: str, content: str) -> Path:
    """Save markdown output to a file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(__file__).parent / "outputs"
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / f"{prompt_name}_{timestamp}.md"
    output_file.write_text(content, encoding="utf-8")

    return output_file


def save_json_output(prompt_name: str, data: dict) -> Path:
    """Save JSON output to a file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(__file__).parent / "outputs"
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / f"{prompt_name}_{timestamp}.json"
    output_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    return output_file


async def generate_documentation(repo_path: str, prompt_name: str):
    """
    Generate documentation for a codebase using a specified prompt.

    Args:
        repo_path: Absolute path to the repository to analyze
        prompt_name: Name of the prompt to use

    Returns:
        Path to the output file
    """
    # Validate prompt name
    if prompt_name not in prompts:
        available_prompts = ", ".join(prompts.keys())
        print(f"❌ Error: Unknown prompt name '{prompt_name}'")
        print(f"Available prompts: {available_prompts}")
        sys.exit(1)

    # Validate repo path
    repo_path_obj = Path(repo_path)
    if not repo_path_obj.exists():
        print(f"❌ Error: Repository path does not exist: {repo_path}")
        sys.exit(1)

    if not repo_path_obj.is_dir():
        print(f"❌ Error: Repository path is not a directory: {repo_path}")
        sys.exit(1)

    prompt_config = prompts[prompt_name]

    print(f"🚀 Starting documentation generation...")
    print(f"   Repo: {repo_path}")
    print(f"   Prompt: {prompt_name}")
    print(f"   Description: {prompt_config.get('description', 'N/A')}")
    print()

    try:
        # Check if this is a markdown prompt or structured prompt
        if prompt_config["schema"] is None:
            # Markdown prompt (overview, frontend)
            print(f"📝 Generating markdown documentation...")
            result = await query_codebase_markdown(
                user_query=prompt_config["prompt_template"],
                repo_path=repo_path,
            )

            # Save markdown output
            output_file = save_markdown_output(prompt_name, result)
            print(f"✅ Success! Markdown saved to: {output_file}")
            print(f"   Size: {len(result)} characters")

        else:
            # Structured prompt (api, data_model)
            print(f"🔧 Generating structured JSON documentation...")
            result = await query_codebase_json(
                user_query=prompt_config["prompt_template"],
                repo_path=repo_path,
                response_model=prompt_config["schema"],
            )

            # Convert Pydantic model to dict
            result_dict = result.model_dump()

            # Save JSON output
            output_file = save_json_output(prompt_name, result_dict)
            print(f"✅ Success! JSON saved to: {output_file}")
            print(f"   Size: {len(json.dumps(result_dict))} characters")

        return output_file

    except ValueError as e:
        print(f"❌ Error: Agent response validation failed")
        print(f"   {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}")
        print(f"   {str(e)}")
        sys.exit(1)


def main():
    """Main entry point for the script."""
    if len(sys.argv) != 3:
        print("Usage: python scripts/generate_documentation.py <repo_path> <prompt_name>")
        print()
        print("Available prompts:")
        for name, config in prompts.items():
            output_type = "Markdown" if config["schema"] is None else "JSON"
            print(f"  • {name:20s} ({output_type:8s}) - {config.get('description', 'N/A')}")
        print()
        print("Examples:")
        print("  python scripts/generate_documentation.py /path/to/repo api")
        print("  python scripts/generate_documentation.py /path/to/repo frontend")
        sys.exit(1)

    repo_path = sys.argv[1]
    prompt_name = sys.argv[2]

    # Run the async function
    asyncio.run(generate_documentation(repo_path, prompt_name))


if __name__ == "__main__":
    main()
