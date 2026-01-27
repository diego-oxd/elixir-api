# Knowledge Extraction API

API for managing projects, pages, code samples, and documentation.

## Setup Required

### Prerequisites

- Python 3.12 or higher
- Docker and Docker Compose

### Dependencies

- FastAPI >= 0.115.0
- Pydantic >= 2.0.0
- PyMongo >= 4.6.0
- Uvicorn >= 0.30.0

## How to Run the API Locally

### 1. Start the Database

The API uses FerretDB (MongoDB-compatible) with PostgreSQL as the backend. Start it with Docker Compose:

```bash
docker-compose up -d
```

This starts:
- PostgreSQL on port 5432 (internal)
- FerretDB on port 27017 (MongoDB protocol)

### 2. Configure Environment Variables

Copy the example environment file and adjust if needed:

```bash
cp .env.example .env
```

Environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `MONGODB_URI` | MongoDB connection string | `mongodb://localhost:27017` |
| `MONGODB_DATABASE` | Database name | `app` |

### 3. Install Dependencies

```bash
pip install -e .
```

For development dependencies:

```bash
pip install -e ".[dev]"
```

### 4. Run the API

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`.

Interactive documentation is available at `http://localhost:8000/docs`.

---

## API Specification

### Root

#### `GET /`

Returns API information.

**Response:**
```json
{
  "message": "Knowledge Extraction API",
  "docs": "/docs"
}
```

---

### Projects

#### `GET /projects`

List all projects.

**Description:** Returns a list of all projects.

**Response:**
```json
[
  {
    "id": "string",
    "name": "string",
    "description": "string | null",
    "repo_path": "string | null"
  }
]
```

---

#### `GET /projects/{project_id}`

Get a project by ID.

**Description:** Returns the full details of a specific project.

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `project_id` | string | The project's unique identifier |

**Response:**
```json
{
  "id": "string",
  "name": "string",
  "description": "string | null",
  "repo_path": "string | null"
}
```

**Errors:**
- `404` - Project not found

---

#### `POST /projects`

Create a new project.

**Description:** Creates a new project with the provided details.

**Request Body:**
```json
{
  "name": "string",
  "description": "string | null",
  "repo_path": "string | null"
}
```

**Response:** `201 Created`
```json
{
  "id": "string",
  "name": "string",
  "description": "string | null",
  "repo_path": "string | null"
}
```

---

#### `PATCH /projects/{project_id}`

Update a project.

**Description:** Updates a project's fields. Only provided fields are updated.

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `project_id` | string | The project's unique identifier |

**Request Body:**
```json
{
  "description": "string | null",
  "repo_path": "string | null"
}
```

**Response:**
```json
{
  "id": "string",
  "name": "string",
  "description": "string | null",
  "repo_path": "string | null"
}
```

**Errors:**
- `400` - No update data provided
- `404` - Project not found

---

#### `DELETE /projects/{project_id}`

Delete a project.

**Description:** Permanently deletes a project.

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `project_id` | string | The project's unique identifier |

**Response:** `204 No Content`

**Errors:**
- `404` - Project not found

---

### Pages

#### `GET /projects/{project_id}/pages/{name}`

Get a page by composite key.

**Description:** Retrieves a page using the combination of project ID and page name.

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `project_id` | string | The project's unique identifier |
| `name` | string | The page's name |

**Response:**
```json
{
  "id": "string",
  "name": "string",
  "title": "string",
  "content": "string",
  "project_id": "string"
}
```

**Errors:**
- `404` - Page not found

---

#### `POST /pages`

Create a new page.

**Description:** Creates a new page associated with a project.

**Request Body:**
```json
{
  "name": "string",
  "title": "string",
  "content": "string",
  "project_id": "string"
}
```

**Response:** `201 Created`
```json
{
  "id": "string",
  "name": "string",
  "title": "string",
  "content": "string",
  "project_id": "string"
}
```

---

#### `PATCH /pages/{page_id}`

Update a page.

**Description:** Updates a page's content. Only provided fields are updated.

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `page_id` | string | The page's unique identifier |

**Request Body:**
```json
{
  "content": "string | null"
}
```

**Response:**
```json
{
  "id": "string",
  "name": "string",
  "title": "string",
  "content": "string",
  "project_id": "string"
}
```

**Errors:**
- `400` - No update data provided
- `404` - Page not found

---

#### `DELETE /pages/{page_id}`

Delete a page.

**Description:** Permanently deletes a page.

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `page_id` | string | The page's unique identifier |

**Response:** `204 No Content`

**Errors:**
- `404` - Page not found

---

### Code Samples

#### `GET /projects/{project_id}/code-samples`

List code samples for a project.

**Description:** Returns all code samples associated with a project (id and title only).

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `project_id` | string | The project's unique identifier |

**Response:**
```json
[
  {
    "id": "string",
    "title": "string"
  }
]
```

---

#### `GET /code-samples/{sample_id}`

Get a code sample by ID.

**Description:** Returns the full details of a specific code sample.

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `sample_id` | string | The code sample's unique identifier |

**Response:**
```json
{
  "id": "string",
  "title": "string",
  "language": "string",
  "description": "string",
  "code_string": "string",
  "project_id": "string"
}
```

**Errors:**
- `404` - Code sample not found

---

#### `POST /code-samples`

Create a new code sample.

**Description:** Creates a new code sample associated with a project.

**Request Body:**
```json
{
  "title": "string",
  "language": "string",
  "description": "string",
  "code_string": "string",
  "project_id": "string"
}
```

**Response:** `201 Created`
```json
{
  "id": "string",
  "title": "string",
  "language": "string",
  "description": "string",
  "code_string": "string",
  "project_id": "string"
}
```

---

#### `PATCH /code-samples/{sample_id}`

Update a code sample.

**Description:** Updates a code sample's fields. Only provided fields are updated.

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `sample_id` | string | The code sample's unique identifier |

**Request Body:**
```json
{
  "title": "string | null",
  "language": "string | null",
  "description": "string | null",
  "code_string": "string | null"
}
```

**Response:**
```json
{
  "id": "string",
  "title": "string",
  "language": "string",
  "description": "string",
  "code_string": "string",
  "project_id": "string"
}
```

**Errors:**
- `400` - No update data provided
- `404` - Code sample not found

---

#### `DELETE /code-samples/{sample_id}`

Delete a code sample.

**Description:** Permanently deletes a code sample.

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `sample_id` | string | The code sample's unique identifier |

**Response:** `204 No Content`

**Errors:**
- `404` - Code sample not found

---

### Doc Pages

#### `GET /projects/{project_id}/doc-pages`

List doc pages for a project.

**Description:** Returns all documentation pages associated with a project (id and title only).

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `project_id` | string | The project's unique identifier |

**Response:**
```json
[
  {
    "id": "string",
    "title": "string"
  }
]
```

---

#### `GET /doc-pages/{doc_page_id}`

Get a doc page by ID.

**Description:** Returns the full details of a specific documentation page.

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `doc_page_id` | string | The doc page's unique identifier |

**Response:**
```json
{
  "id": "string",
  "title": "string",
  "content": "string",
  "project_id": "string"
}
```

**Errors:**
- `404` - Doc page not found

---

#### `POST /doc-pages`

Create a new doc page.

**Description:** Creates a new documentation page associated with a project.

**Request Body:**
```json
{
  "title": "string",
  "content": "string",
  "project_id": "string"
}
```

**Response:** `201 Created`
```json
{
  "id": "string",
  "title": "string",
  "content": "string",
  "project_id": "string"
}
```

---

#### `PATCH /doc-pages/{doc_page_id}`

Update a doc page.

**Description:** Updates a documentation page's fields. Only provided fields are updated.

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `doc_page_id` | string | The doc page's unique identifier |

**Request Body:**
```json
{
  "title": "string | null",
  "content": "string | null"
}
```

**Response:**
```json
{
  "id": "string",
  "title": "string",
  "content": "string",
  "project_id": "string"
}
```

**Errors:**
- `400` - No update data provided
- `404` - Doc page not found

---

#### `DELETE /doc-pages/{doc_page_id}`

Delete a doc page.

**Description:** Permanently deletes a documentation page.

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `doc_page_id` | string | The doc page's unique identifier |

**Response:** `204 No Content`

**Errors:**
- `404` - Doc page not found
