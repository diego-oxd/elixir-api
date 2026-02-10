from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class FrontendOverview(BaseModel):
    """High-level summary of the frontend architecture.

    This should give a developer a quick understanding of the tech stack,
    architectural patterns, and overall structure.
    """

    summary: str = Field(
        ...,
        description="2-3 paragraph overview of the frontend architecture, key patterns, and structure"
    )

    framework: str = Field(
        ...,
        description="Frontend framework and version (e.g., 'React 18.2.0', 'Vue 3.x')"
    )

    state_management: str = Field(
        ...,
        description="State management approach (e.g., 'Redux Toolkit', 'React Context API', 'Vuex', 'local state only')"
    )

    routing_library: str = Field(
        ...,
        description="Routing library and version (e.g., 'react-router-dom v6', 'Vue Router v4', 'Next.js routing')"
    )

    styling_approach: str = Field(
        ...,
        description="Styling approach (e.g., 'CSS Modules', 'Tailwind CSS', 'styled-components', 'SCSS')"
    )

    key_patterns: List[str] = Field(
        default_factory=list,
        description="Important patterns used (e.g., 'Custom hooks for data fetching', 'HOC for authentication', 'Compound components')"
    )

    build_tool: Optional[str] = Field(
        None,
        description="Build tool if notable (e.g., 'Vite', 'webpack', 'Create React App')"
    )


class RouteInfo(BaseModel):
    """Information about a route/page in the application.

    Focuses on what developers need to know: what's the URL, what renders,
    and what data it needs.
    """

    path: str = Field(
        ...,
        description="Route path (e.g., '/dashboard', '/users/:id', '/admin/*')"
    )

    component: str = Field(
        ...,
        description="Main component that renders for this route"
    )

    description: str = Field(
        ...,
        description="What this page/route does (1-2 sentences)"
    )

    auth_required: bool = Field(
        default=False,
        description="Whether this route requires authentication"
    )

    roles: List[str] = Field(
        default_factory=list,
        description="Required roles if auth is enforced (e.g., ['admin', 'editor'])"
    )

    loads_data_from: List[str] = Field(
        default_factory=list,
        description="API endpoints called when route loads (e.g., ['GET /api/users', 'GET /api/stats'])"
    )

    layout: Optional[str] = Field(
        None,
        description="Layout component if using nested layouts"
    )


class ComponentInfo(BaseModel):
    """Information about a frontend component.

    Balanced level of detail - enough to understand the component without
    overwhelming with every prop and state variable.
    """

    name: str = Field(
        ...,
        description="Component name (e.g., 'UserDashboard', 'LoginForm')"
    )

    file_path: str = Field(
        ...,
        description="Relative path to component file (e.g., 'src/pages/Dashboard.tsx')"
    )

    component_type: str = Field(
        ...,
        description="Component type: 'page', 'layout', 'form', 'modal', 'container', 'presentational', or 'utility'"
    )

    purpose: str = Field(
        ...,
        description="What this component does - 2-3 sentences explaining its role and responsibility"
    )

    key_props: List[str] = Field(
        default_factory=list,
        description="Important props with types (e.g., ['userId: string (required)', 'onClose?: () => void', 'data: User[]'])"
    )

    manages_state: List[str] = Field(
        default_factory=list,
        description="Local state variables with types (e.g., ['isLoading: boolean', 'formData: FormState', 'error: string | null'])"
    )

    uses_global_state: List[str] = Field(
        default_factory=list,
        description="Global state or context used (e.g., ['currentUser from UserContext', 'theme from ThemeContext'])"
    )

    api_calls: List[Dict[str, str]] = Field(
        default_factory=list,
        description="API calls made by this component. Each dict should have 'endpoint' and 'trigger' keys. "
                    "Example: [{'endpoint': 'GET /api/users', 'trigger': 'on mount'}, {'endpoint': 'POST /api/login', 'trigger': 'on form submit'}]"
    )

    rendered_in: List[str] = Field(
        default_factory=list,
        description="Where this component is used - route paths or parent component names (e.g., ['/dashboard', 'AdminLayout'])"
    )

    child_components: List[str] = Field(
        default_factory=list,
        description="Child components rendered (e.g., ['UserCard', 'LoadingSpinner', 'ErrorBoundary'])"
    )

    hooks_used: List[str] = Field(
        default_factory=list,
        description="Custom hooks or important built-in hooks (e.g., ['useAuth', 'useQuery', 'useEffect for data fetching'])"
    )

    notes: Optional[str] = Field(
        None,
        description="Additional notes, gotchas, or important details developers should know"
    )


class FrontendDocumentation(BaseModel):
    """Complete frontend documentation output.

    Provides a comprehensive but readable overview of the frontend architecture,
    routes, and components.
    """

    overview: FrontendOverview = Field(
        ...,
        description="High-level architectural overview"
    )

    routes: List[RouteInfo] = Field(
        default_factory=list,
        description="All routes/pages in the application"
    )

    components: List[ComponentInfo] = Field(
        default_factory=list,
        description="Key components - should include all page components, layouts, and important shared components"
    )

    important_files: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Other important files to know about. Each dict should have 'path' and 'description'. "
                    "Example: [{'path': 'src/utils/api.ts', 'description': 'Axios wrapper with auth headers'}, "
                    "{'path': 'src/hooks/useAuth.ts', 'description': 'Authentication hook'}]"
    )


class OutputSchema(BaseModel):
    """Final output structure."""

    documentation_notes: str = Field(
        ...,
        description="Brief notes about the documentation generation - any limitations, assumptions, or areas that need manual review"
    )

    frontend_schema: FrontendDocumentation = Field(
        ...,
        description="Complete frontend documentation"
    )


prompt_template = """
# Frontend Architecture Documentation

## Objective

Create comprehensive yet readable documentation of the frontend codebase that helps developers quickly understand:
1. What pages/routes exist and what they do
2. The main components and their responsibilities
3. How data flows from UI to backend APIs
4. The overall architecture and patterns used

**Focus on clarity and usefulness over exhaustive detail.**

## Analysis Approach

### Step 1: Understand the Tech Stack (5 minutes)

Identify:
- Frontend framework and version (React, Vue, Angular, Svelte, etc.)
- State management approach (Redux, Context, Vuex, Pinia, local state, etc.)
- Routing library (react-router, Vue Router, Next.js, etc.)
- Styling approach (CSS Modules, Tailwind, styled-components, SCSS, etc.)
- Build tool if notable (Vite, webpack, Parcel, etc.)

**How to find it:**
- Check `package.json` for dependencies
- Look for config files (vite.config, webpack.config, next.config, etc.)
- Read README or main.tsx/main.js

### Step 2: Map the Routes (10 minutes)

Find all route definitions and document:
- Route paths (URLs)
- Which component renders
- Brief description of what the page does
- Whether authentication is required
- What data loads on page entry

**How to find it:**
- React Router: Look for `<Route>` components, often in `App.tsx` or `routes.tsx`
- Vue Router: Check `router/index.ts` or `router.js`
- Next.js: Look at `pages/` or `app/` directory structure
- Check for `ProtectedRoute` or auth wrappers

### Step 3: Document Key Components (20-30 minutes)

For each major component (focus on pages, layouts, and shared components):

**Identify:**
- Component name and file location
- What it does (2-3 sentence description)
- Component type (page, layout, form, etc.)

**Capture Key Interfaces:**
- Important props (name and type, note if required)
- Local state it manages (name and type)
- Global state/context it uses

**Trace Data Flow:**
- API endpoints it calls
- When those calls happen (on mount, on button click, etc.)
- What triggers re-renders

**Map Relationships:**
- What routes render this component
- What child components it renders
- Custom hooks it uses

**Pro tips:**
- Read the component file itself - don't guess
- Use semantic search to find API calls and state usage
- Check for TypeScript interfaces or PropTypes for accurate types
- Note any important patterns or gotchas in the notes field

### Step 4: Identify Patterns (5 minutes)

Note recurring patterns:
- Custom hooks for data fetching
- HOCs for authentication/authorization
- Render props patterns
- Component composition strategies
- Error boundary usage
- Code splitting approaches

## Output Format

Return a JSON document following the schema exactly. Here's an example:

```json
{
  "documentation_notes": "This documentation covers the main user-facing routes and components. The admin section has additional components not fully documented here. Some API endpoints are inferred from network calls.",

  "frontend_schema": {
    "overview": {
      "summary": "This is a React 18 single-page application using react-router-dom for routing and Context API for state management. The app follows a container/presentational component pattern with custom hooks for data fetching. Authentication is handled via JWT tokens stored in localStorage and validated on protected routes.",

      "framework": "React 18.2.0",
      "state_management": "React Context API (UserContext, ThemeContext) + local state with useState",
      "routing_library": "react-router-dom v6",
      "styling_approach": "CSS Modules with SCSS",
      "build_tool": "Vite",

      "key_patterns": [
        "Custom useApi hook for all backend calls with automatic auth headers",
        "ProtectedRoute wrapper for authenticated pages",
        "Suspense with lazy loading for code splitting",
        "Error boundaries at route level"
      ]
    },

    "routes": [
      {
        "path": "/",
        "component": "HomePage",
        "description": "Landing page with hero section and feature overview",
        "auth_required": false,
        "roles": [],
        "loads_data_from": []
      },
      {
        "path": "/dashboard",
        "component": "Dashboard",
        "description": "Main user dashboard showing stats, recent activity, and quick actions",
        "auth_required": true,
        "roles": ["user", "admin"],
        "loads_data_from": [
          "GET /api/user/profile",
          "GET /api/dashboard/stats"
        ],
        "layout": "MainLayout"
      },
      {
        "path": "/users/:userId",
        "component": "UserProfile",
        "description": "User profile page showing user details and activity history",
        "auth_required": true,
        "roles": ["admin"],
        "loads_data_from": [
          "GET /api/users/:userId",
          "GET /api/users/:userId/activity"
        ],
        "layout": "MainLayout"
      }
    ],

    "components": [
      {
        "name": "Dashboard",
        "file_path": "src/pages/Dashboard.tsx",
        "component_type": "page",
        "purpose": "Main dashboard page that displays user statistics, recent activity feed, and quick action buttons. Coordinates data fetching and delegates rendering to child components.",

        "key_props": [],

        "manages_state": [
          "stats: DashboardStats | null",
          "activity: Activity[]",
          "loading: boolean",
          "error: string | null"
        ],

        "uses_global_state": [
          "currentUser from UserContext",
          "theme from ThemeContext"
        ],

        "api_calls": [
          {
            "endpoint": "GET /api/dashboard/stats",
            "trigger": "on mount"
          },
          {
            "endpoint": "GET /api/activity/recent",
            "trigger": "on mount"
          },
          {
            "endpoint": "POST /api/activity/mark-read",
            "trigger": "when user clicks 'Mark as Read' button"
          }
        ],

        "rendered_in": ["/dashboard"],

        "child_components": [
          "StatsCard",
          "ActivityFeed",
          "QuickActions",
          "LoadingSpinner"
        ],

        "hooks_used": [
          "useApi (custom hook)",
          "useAuth (custom hook)",
          "useEffect for data fetching"
        ],

        "notes": "This component uses the useApi hook which handles loading/error states automatically. The stats refresh every 30 seconds via polling."
      },
      {
        "name": "MainLayout",
        "file_path": "src/layouts/MainLayout.tsx",
        "component_type": "layout",
        "purpose": "Main application layout wrapper that provides navigation, header, sidebar, and footer. Wraps all authenticated pages.",

        "key_props": [
          "children: React.ReactNode (required)"
        ],

        "manages_state": [
          "sidebarOpen: boolean"
        ],

        "uses_global_state": [
          "currentUser from UserContext"
        ],

        "api_calls": [],

        "rendered_in": [
          "All authenticated routes"
        ],

        "child_components": [
          "Header",
          "Sidebar",
          "Footer"
        ],

        "hooks_used": [
          "useAuth"
        ],

        "notes": "Sidebar state persists in localStorage. Shows different nav items based on user role."
      },
      {
        "name": "useApi",
        "file_path": "src/hooks/useApi.ts",
        "component_type": "utility",
        "purpose": "Custom hook that wraps fetch calls with automatic auth token injection, loading states, and error handling. Returns data, loading, error, and a refetch function.",

        "key_props": [],
        "manages_state": [],
        "uses_global_state": [],
        "api_calls": [],
        "rendered_in": [],
        "child_components": [],
        "hooks_used": [],

        "notes": "Used by almost all components that fetch data. Automatically refreshes auth token if expired. Exports TypeScript types for common API responses."
      }
    ],

    "important_files": [
      {
        "path": "src/contexts/UserContext.tsx",
        "description": "Global user state - provides currentUser, login, logout functions"
      },
      {
        "path": "src/utils/api.ts",
        "description": "Axios instance with base URL and interceptors"
      },
      {
        "path": "src/types/index.ts",
        "description": "TypeScript type definitions for API responses and models"
      }
    ]
  }
}
```

## Important Guidelines

### Do's ✅

- **Read actual source files** - Use the read_file tool extensively
- **Be specific** - Include actual prop types, state variable names, API endpoints
- **Focus on main components** - Pages, layouts, forms, and widely-used shared components
- **Use natural language** - Descriptions should be clear and conversational
- **Note patterns** - Developers care about conventions and patterns
- **Include gotchas** - Use the notes field for important warnings or quirks

### Don'ts ❌

- **Don't guess** - If you can't find information, say so in documentation_notes
- **Don't document every component** - Focus on the important ones (aim for 10-30 components)
- **Don't over-detail** - We want key props, not every single prop
- **Don't fabricate types** - If you can't determine the exact type, describe it in plain English
- **Don't skip API endpoints** - These are critical for understanding data flow

### Quality Checklist

Before submitting, verify:
- [ ] All routes are documented
- [ ] Main page components are included
- [ ] API endpoints are mapped to components
- [ ] Component relationships are clear (what renders what)
- [ ] State management approach is explained
- [ ] Key patterns are noted
- [ ] Descriptions are helpful and specific

## Tool Usage

Use these tools effectively:

1. **query_codebase_knowledge_graph** - Find components, routes, files
   - "Find all React components"
   - "Show me files in the src/pages directory"
   - "Find components that use useState"

2. **read_file_content** - Read source files
   - Read route definitions
   - Read component files
   - Read package.json for dependencies

3. **semantic_code_search** - Find patterns
   - "Find API calls"
   - "Find authentication logic"
   - "Find state management setup"

4. **analyze_document** - For README or architecture docs
   - Get high-level overview
   - Understand intended patterns

Remember: You're helping a developer understand a new codebase quickly. Focus on what they need to know to start being productive.
"""


frontend_prompt = {
    "name": "frontend",
    "description": "Documents frontend architecture, routes, components, and data flow in a developer-friendly format.",
    "prompt_template": prompt_template,
    "schema": OutputSchema,
}
