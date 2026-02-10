from pydantic import BaseModel

overview_prompt_template = """
# Codebase Onboarding & Familiarization Prompt

## Primary Objective
Provide a comprehensive but concise overview of this codebase to enable a new developer to understand the architecture, navigate the project effectively, and start contributing with confidence.

## Analysis Instructions
Analyze the codebase and provide a structured onboarding guide that covers:

1. **Project Identity & Purpose**
   - What does this application do? 

2. **Technology Stack**
   - Framework(s) and versions
   - Database/storage technology
   - Key libraries and their purposes
   - Build tools and package managers

3. **Architecture Overview**
   - High-level architectural pattern
   - How the application is structured (client/server, layers, modules)
   - Data flow: How information moves through the system
   - External dependencies and integrations

4. **Project Structure**
   - Directory organization and naming conventions
   - Where to find: routes/endpoints, business logic, data models, UI components, tests, configs
   - Important files that define the application (entry points, config files)

5. **Framework-Specific Patterns**
   - How does this framework structure applications?
   - Common patterns used in this codebase
   - Framework-specific conventions to be aware of

6. **Navigation Guide**
   - A suggested walkthrough path for exploring the codebase
   - Key files to read first
   - Typical workflow: "If you need to add X, you would modify Y"

## Output Format

Provide output as a Markdown document with the following structure:

```markdown
# Codebase Overview

## Quick Summary
[2-3 sentences describing what this application does and its core purpose]

**Tech Stack:** [Framework] + [Database] + [Key Libraries]  
**Architecture:** [Pattern Type]  
**Last Updated:** [If version info available]
---

## Architecture at a Glance

### System Design
[2-4 sentences explaining the high-level architecture]

### Data Flow
[Brief explanation of how data moves through the system, e.g., "User action → API endpoint → Database → Real-time update"]

### Key Integrations
- **[Integration Name]**: [Purpose]
- **[Integration Name]**: [Purpose]

---
## Project Structure
```
project-root/
├── [directory]/          # [Purpose]
├── [directory]/          # [Purpose]
│   ├── [subdirectory]/   # [Purpose]
│   └── [subdirectory]/   # [Purpose]
└── [directory]/          # [Purpose]
```
### Where to Find What

| Need to... | Look in... |
|------------|-----------|
| Add a new API endpoint | `[path]` |
| Modify data schema | `[path]` |
| Update UI components | `[path]` |
| Add business logic | `[path]` |
| Configure environment | `[path]` |
---

## Technology Stack

### Core Framework: [Framework Name]
[1-2 sentences about how this framework works and its key characteristics]

### Database: [Database Name]
[1 sentence about the database and how it's used]

### Key Dependencies
- **[Library]** - [What it does in this project]
- **[Library]** - [What it does in this project]
- **[Library]** - [What it does in this project]
---

## Framework Patterns & Conventions

### [Framework Name] Conventions
- **[Pattern Name]**: [How it's used in this project]
- **[Pattern Name]**: [How it's used in this project]

### Project-Specific Patterns
- **[Custom Pattern]**: [Explanation and why it exists]
- **[Custom Pattern]**: [Explanation and why it exists]

### Naming Conventions
- **Files**: [Convention, e.g., camelCase, kebab-case]
- **Components**: [Convention]
- **APIs/Methods**: [Convention]
---

## Guided Walkthrough

**Step 1: Start Here**
- 📄 `[file path]` - [Why: This file does X and shows Y]
- 📄 `[file path]` - [Why: This defines Z]

**Step 2: Understand Data Flow**
- 📄 `[file path]` - [Where data is defined]
- 📄 `[file path]` - [Where data is accessed]
- 📄 `[file path]` - [Where data is displayed]
---

## Things to Know
### Helpful Patterns
- [Pattern or convention that makes development easier]
- [Another helpful thing to know]

### Watch Out For
- [Gotcha or quirk to be aware of]
- [Technical debt or legacy pattern]

### Security Considerations
- [How authentication works]
- [How authorization is handled]

## Follow up questions
- What are things that I should 
---
```

## Key Requirements

- **Brevity**: Keep each section concise (2-4 sentences max per explanation)
- **Actionable**: Provide specific file paths, not vague directions
- **Progressive**: Start simple, layer in complexity
- **Visual**: Use directory trees, tables, and formatting for scannability
- **Practical**: Include real examples from the codebase
- **Friendly**: Write for someone who's capable but unfamiliar with this specific project

## Tone Guidelines
- Welcoming,  but not overwhelming
- Assume competence but provide context
- Focus on "what you need to know" not "everything about the codebase"
- Highlight patterns that will help them navigate independently
- Use emojis sparingly for visual anchors (📁 🔧 🗺️ etc.)

## Validation Checklist
Before returning the onboarding guide, verify:
- [ ] All file paths mentioned actually exist in the codebase
- [ ] The walkthrough provides a logical learning path
- [ ] Framework-specific patterns are accurately described
- [ ] "Where to Find What" table is comprehensive but not exhaustive
- [ ] The guide is easy to follow and skimmable
- [ ] Code examples (if included) are real snippets from the project
- [ ] Technical terms are explained when first introduced
"""


class OutputSchema(BaseModel):
    overview_notes: str
    full_overview_document: str


project_overview_prompt = {
    "name": "project_overview",
    "description": "Provides a comprehensive overview of the entire codebase, including architecture, data flow, key components, and technology stack.",
    "prompt_template": overview_prompt_template,
    "schema": OutputSchema,
}
