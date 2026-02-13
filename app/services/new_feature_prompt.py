prompt_template = """

# Feature Implementation Guide

## Feature Requirements

{requirements}

## Analysis Instructions

Analyze this codebase to create an implementation guide for the above feature. Structure your response in three sections:

### 1. Affected Components

Identify all code modules impacted by this feature.

**Output Format:**
```markdown
## Affected Components

### Frontend Components
- **`path/to/component.jsx`** - Brief description of relevance
- **`path/to/component.jsx`** - Brief description of relevance

### Backend Endpoints/Methods
- **`endpoint.name`** in `path/to/file.js` - Brief description of relevance
- **`method.name`** in `path/to/file.js` - Brief description of relevance

### Data Storage
- **Collection/Table Name** in `path/to/schema.js` - What needs to change

### State Management
- **Store/Context** in `path/to/file.js` - What needs to change

### Utilities/Services
- **Function/Service** in `path/to/file.js` - Brief description of relevance

**Scope:** [single module | multiple related modules | cross-cutting change]
```

---

### 2. Implementation Flow

Map out how the feature works through the system, including interaction patterns and data flow.

**Output Format:**
```markdown
## Implementation Flow

### Similar Existing Feature
**Feature Name:** [name]
**Location:** `path/to/files`
**Relevance:** [How it's similar and what can be reused]

### Data Flow for New Feature

#### Step 1: User Interaction
- **UI Component:** `path/to/component.jsx`
- **Action:** [What user does]
- **State Changes:** [What local/global state updates]

#### Step 2: API Call
- **Endpoint/Method:** `endpoint.name`
- **File:** `path/to/file.js`
- **Input:** [Request payload shape]
- **Validation:** [What gets validated]

#### Step 3: Backend Processing
- **Business Logic:** `path/to/file.js`
- **Operations:** [What happens - checks, transforms, etc]
- **External Services:** [Any external calls]

#### Step 4: Data Persistence
- **Collection/Table:** [Name]
- **Operation:** [Insert/Update/Delete]
- **Changes:** [What fields are affected]

#### Step 5: Response & UI Update
- **Success Response:** [What gets returned]
- **State Updates:** [What re-renders]
- **Side Effects:** [Navigation, notifications, etc]
- **Error Handling:** [How errors are shown]

### Key Interaction Patterns
- [Pattern 1: e.g., "Form validation happens client-side before API call"]
- [Pattern 2: e.g., "Optimistic UI updates with rollback on error"]
- [Pattern 3: e.g., "Real-time updates via subscription"]
```

---

### 3. Impact Analysis

Identify potential issues, edge cases, and affected areas.

**Output Format:**
```markdown
## Impact Analysis

### Areas of Concern
- **[Module/Feature Name]**: [Why it might be affected]
- **[Module/Feature Name]**: [Why it might be affected]

### Edge Cases to Consider
- [Edge case 1 with brief explanation]
- [Edge case 2 with brief explanation]
- [Edge case 3 with brief explanation]

### Possible Side Effects
- **Performance**: [Any performance implications]
- **Security**: [Any security considerations]
- **Data Integrity**: [Any data consistency concerns]
- **User Experience**: [Any UX impacts]

### Required Changes in Related Features
- **[Feature Name]**: [What needs to be updated]
- **[Feature Name]**: [What needs to be updated]

### Testing Recommendations
- Unit tests needed in: [files/modules]
- Integration tests for: [workflows]
- Edge cases to test: [specific scenarios]
```

---

## Analysis Guidelines

**When identifying components:**
- Search by keywords from requirements in file names, component names, function names
- Check frontend components if feature involves UI
- Check backend methods/endpoints if feature involves data operations
- Include both direct dependencies and indirect impacts

**When mapping data flow:**
- Start from user interaction (if applicable)
- Follow the path through each layer
- Note all state changes and side effects
- Reference similar existing features when found

**When analyzing impact:**
- Consider authentication/authorization changes
- Check for breaking changes to existing APIs
- Identify performance implications
- Note any migration or backward compatibility needs

**Keep it actionable:**
- Provide specific file paths, not vague locations
- Describe concrete changes, not abstract concepts
- Prioritize information by implementation order
- Flag blockers or dependencies clearly

If any items in the output format or the analysis guideline 
is not applicable to this feature, you can just ignore them.
"""