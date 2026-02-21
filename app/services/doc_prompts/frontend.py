prompt_template = """
# Frontend Architecture Documentation

## Objective

You are a senior developer writing onboarding documentation for a new team member joining this project. Your goal is to produce a single markdown document that gives them everything they need to:

1. Understand how the frontend is structured and where to find things
2. Follow existing patterns and conventions when making changes
3. Understand how data flows between the UI and backend
4. Know what features/pages exist at a high level

**Write for a competent developer who doesn't know this codebase yet.** Be specific and concrete — reference actual file paths, actual function names, actual endpoints. But don't be exhaustive. Focus on what they need to be productive, not on cataloguing every file.

## Output Format

Produce a single markdown document with the following sections, in this order. Use clear prose — not JSON, not bullet-point dumps. Tables where they help scannability, paragraphs where explanation matters.

---

### Section 1: Overview (brief)

A 2-3 paragraph introduction covering:
- What the app is and what it does (from the frontend's perspective)
- Tech stack: framework, language, styling, state management, routing, build tool
- Architectural philosophy in one sentence (e.g., "Feature-based folder structure with colocated styles and tests" or "Pages fetch data via custom hooks and pass down to presentational components")

This should read like the opening of a good README.

### Section 2: Project Structure

An annotated directory tree of the `src/` folder (or equivalent). Go 2-3 levels deep. For each significant directory, include a one-line description of what lives there.

Example format:
```
src/
├── pages/              # Page-level components, one per route
│   ├── Dashboard/
│   ├── Settings/
│   └── Auth/
├── components/         # Shared/reusable UI components
│   ├── forms/
│   ├── layout/
│   └── common/
├── hooks/              # Custom React hooks
├── contexts/           # React Context providers
├── services/           # API client and service layer
├── utils/              # Helper functions
├── types/              # TypeScript type definitions
└── styles/             # Global styles and theme
```

After the tree, add a short paragraph about naming conventions and file organization patterns (e.g., "Each page folder contains the page component, its styles, and any sub-components specific to that page").

### Section 3: Patterns & Conventions

This is the "how to do things" section. Cover the key patterns a developer needs to follow, organized as subsections. Only include patterns that actually exist in the codebase. Common ones to look for:

- **Adding a new page/route**: Where to define routes, how to register a new page, any wrappers needed (auth, layout).
- **Data fetching**: What's the standard approach? Custom hook? Service layer? Direct fetch calls? Show the typical pattern with a real example from the codebase.
- **Authentication & authorization**: How auth state is managed, how protected routes work, how to check permissions.
- **Styling**: What's the convention? How to add styles to a new component.
- **Forms**: If there's a form pattern (e.g., React Hook Form, Formik, custom), explain it.
- **Error handling**: How errors from API calls are caught and displayed.

For each pattern, briefly describe it and reference the actual files/functions involved. If there's a good example in the codebase, point to it by file path.

### Section 4: State Management

Explain:
- What global state exists and where it's defined (contexts, stores, etc.)
- What each piece of global state is responsible for (e.g., "UserContext holds the current user session and exposes login/logout methods")
- When to use global state vs. local state (if there's a clear convention)

Keep this concise. A short paragraph per context/store is plenty.

### Section 5: API Integration

Cover:
- Where the API client lives and how it's configured (base URL, auth headers, interceptors)
- The standard pattern for making API calls from components
- How API errors are handled
- A few concrete examples of data flow: "When the user opens the Dashboard, `DashboardPage` calls `GET /api/stats` via the `useStats` hook, which returns `{ data, loading, error }`"

Include 3-5 representative data flow examples that show different patterns (read on mount, form submission, real-time updates, etc.).

### Section 6: Pages & Features

Group pages by feature area. For each group, write a brief narrative (2-4 sentences) explaining what the feature does, then list the routes in a table.

Example format:

#### Authentication
Handles user login, registration, and password recovery. Uses JWT tokens stored in localStorage. After login, the user is redirected to the dashboard.

| Route | Component | Description | Auth |
|-------|-----------|-------------|------|
| `/login` | `LoginPage` | Email/password login form | No |
| `/register` | `RegisterPage` | New user registration | No |
| `/forgot-password` | `ForgotPasswordPage` | Password reset request | No |

#### Dashboard
The main landing page after login. Shows summary stats and recent activity.

| Route | Component | Description | Auth |
|-------|-----------|-------------|------|
| `/dashboard` | `DashboardPage` | Stats overview and activity feed | Yes |
| `/dashboard/activity` | `ActivityPage` | Detailed activity history | Yes |

### Section 7: Key Shared Components (slim)

Only document shared components that a new developer is likely to need or encounter frequently — things like layout wrappers, form components, data tables, modals, or other building blocks used across multiple pages.

For each, provide:
- **Name and file path**
- **What it does** (1-2 sentences)
- **When to use it** (1 sentence)

Don't document page-specific sub-components, simple presentational wrappers, or anything that's self-explanatory from its name and code.

### Section 8: Important Files Quick Reference

A simple table of files a new developer should know about, with one-line descriptions. Think: "If I could only bookmark 10-15 files, which ones?"

| File | Why it matters |
|------|---------------|
| `src/App.tsx` | Root component, route definitions |
| `src/services/api.ts` | API client setup, auth interceptors |
| ... | ... |

---

## Analysis Instructions

To produce this documentation, follow this process:

1. **Start with `package.json`** — identify the framework, key libraries, and versions.
2. **Read the entry point** (`main.tsx`, `index.tsx`, `App.tsx`) — understand the app shell, providers, and route structure.
3. **Map the `src/` directory** — understand the folder structure before diving into files.
4. **Read the route definitions** — find every route and what component it maps to.
5. **Read key infrastructure files** — API client, auth logic, context providers, custom hooks.
6. **Read page components** — understand what each page does and what data it needs.
7. **Identify shared components** — find reusable components used across multiple pages.
8. **Synthesize patterns** — based on what you've read, identify the conventions the codebase follows.

**Critical rules:**
- Read actual source files. Do not guess or infer what code does.
- If you can't determine something, say so explicitly rather than fabricating.
- Reference real file paths and real function/component names.
- Write for humans, not machines. This is prose documentation, not a data dump.
- Keep the total document focused. Aim for something that can be read in 15-20 minutes.

## CRITICAL: Markdown Output Format

**IMPORTANT**: Your response must be PURE MARKDOWN ONLY. Do NOT wrap it in JSON or any other format.

Guidelines for markdown formatting:
- Use standard markdown syntax (headers, lists, code blocks, tables)
- Avoid characters that could cause parsing issues when stored/transmitted
- For code blocks, use triple backticks with language identifiers
- For inline code or technical terms, use single backticks
- For emphasis, prefer **bold** over quotes
- If you need quotes in text, prefer single quotes (') or backticks (`) over double quotes (")
- Ensure proper escaping of special markdown characters when needed
- The output will be stored as plain text and rendered by a markdown parser

The markdown should be ready for immediate display in a markdown renderer without any additional processing.
"""


frontend_prompt = {
    "name": "frontend",
    "description": "Documents frontend architecture, routes, components, and data flow in a developer-friendly format.",
    "prompt_template": prompt_template,
    "schema": None,  # Returns raw markdown, not structured JSON
}
