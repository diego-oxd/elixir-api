# Scripts

This directory contains utility scripts for the knowledge extraction API.

## generate_documentation.py

Standalone script to generate documentation for a codebase using Claude Agent SDK.

### Overview

This script mirrors the functionality of the `/code-query/generate-docs` endpoint but can be run directly from the command line. It uses the same prompts and agent configuration as the API endpoint.

### Usage

```bash
python scripts/generate_documentation.py <repo_path> <prompt_name>
```

**Arguments:**
- `repo_path`: Absolute path to the repository you want to analyze
- `prompt_name`: Name of the documentation prompt to use

### Available Prompts

| Prompt Name | Output Format | Description |
|------------|---------------|-------------|
| `api` | JSON | Analyzes API endpoints and provides detailed information about their structure and functionality |
| `data_model` | JSON | Analyzes and documents a codebase's complete data model structure |
| `frontend` | Markdown | Documents frontend architecture, routes, components, and data flow |
| `project_overview` | Markdown | Provides a comprehensive overview of the entire codebase |

### Examples

Generate API documentation:
```bash
python scripts/generate_documentation.py /path/to/my-repo api
```

Generate frontend documentation:
```bash
python scripts/generate_documentation.py /path/to/my-repo frontend
```

Generate project overview:
```bash
python scripts/generate_documentation.py /path/to/my-repo project_overview
```

### Output Files

All generated documentation is saved to the `scripts/outputs/` directory with timestamped filenames:

- **Markdown prompts**: `outputs/<prompt_name>_<timestamp>.md`
- **JSON prompts**: `outputs/<prompt_name>_<timestamp>.json`

Example output files:
- `outputs/frontend_20260212_143025.md`
- `outputs/api_20260212_143125.json`

### How It Works

1. **Validates inputs**: Checks that the prompt name exists and the repo path is valid
2. **Loads prompt configuration**: Uses the same prompts defined in `app/services/prompts.py`
3. **Invokes Claude Agent SDK**: Calls either `query_codebase_markdown()` or `query_codebase_json()` depending on the prompt type
4. **Saves output**: Writes the result to a timestamped file in `scripts/outputs/`

The script uses the Claude Agent SDK with the following tools:
- `Read`: Read file contents
- `Glob`: Find files by pattern
- `Grep`: Search for content in files

### Requirements

This script uses the same dependencies as the main application. Make sure you have:
- Python 3.11+
- All packages from `requirements.txt` installed
- `ANTHROPIC_API_KEY` environment variable set

### Logging

Agent responses are logged to `logs/agent_responses/` for debugging purposes (same as the API endpoint).

### Error Handling

The script will exit with a non-zero status code and display an error message if:
- Invalid prompt name is provided
- Repository path doesn't exist or isn't a directory
- Agent fails to generate valid output
- Schema validation fails (for JSON prompts)

### Troubleshooting

**Q: Script fails with "Module not found" error**
A: Make sure you're running the script from the project root directory and all dependencies are installed.

**Q: Agent returns invalid output**
A: Check the log files in `logs/agent_responses/` for details about what went wrong. The error message will include the log file path.

**Q: Documentation generation is slow**
A: This is normal. Complex codebases can take 30-90 seconds to analyze. The Claude Agent SDK needs to explore the codebase using file operations.

## Other Scripts

- `test.py`: Test script for development
- `load_page.py`: Script to load page data
- `init_db.sql`: Database initialization SQL script
