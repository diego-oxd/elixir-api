from pydantic import BaseModel
from typing import List, Optional, Literal


class Field(BaseModel):
    """Simplified field representation - just the essentials"""
    name: str
    data_type: str
    required: bool
    description: Optional[str] = None


class Relationship(BaseModel):
    """Simple relationship representation"""
    related_to: str  # Name of the related collection/table
    relationship_type: str  # e.g., "one-to-many", "many-to-one", "many-to-many"
    description: Optional[str] = None


class Collection(BaseModel):
    """Represents a single data storage entity (collection/table/store)"""
    name: str
    type: str  # e.g., "collection", "table", "view", "cache"
    purpose: str  # Brief description of what this stores
    fields: List[Field]
    relationships: List[Relationship]


class DataModel(BaseModel):
    """Complete data model documentation"""
    overview: str  # High-level description of the data model, its purpose, and how to use it
    framework: str  # e.g., "Meteor", "Express + Mongoose", "Django"
    database: str  # e.g., "MongoDB", "PostgreSQL", "Redis"
    collections: List[Collection]


prompt_template = """
# Data Model Documentation Task

## Objective
Analyze the codebase and create complete documentation of its data model. Document every collection/table with all of its fields, showing what data exists and how it connects together.

## What to Extract

### 1. System Overview
- What framework is being used? (e.g., Meteor, Express, Django, Rails)
- What database technology? (e.g., MongoDB, PostgreSQL, Redis)
- Brief overview: What is this data model for? What's its main purpose?

### 2. For Each Collection/Table
Extract:
- **Name**: The collection or table name
- **Type**: Collection, table, view, cache, or other storage type
- **Purpose**: One sentence explaining what data this stores
- **Fields**: Every field/column with:
  - Field name
  - Data type (string, number, boolean, date, array, object, etc.)
  - Whether it's required
  - Brief description (if helpful for understanding)
- **Relationships**: How this connects to other collections:
  - Which collection it relates to
  - Type of relationship (one-to-many, many-to-one, many-to-many, etc.)
  - Brief description of the relationship

## Where to Look
- `/models`, `/schemas`, `/collections`, `/entities`, `/api` directories
- Schema definition files
- Database migration files
- ORM/ODM model definitions

## What NOT to Extract
- Skip: indexes, constraints, default values, validators
- Skip: implementation details like middleware or hooks
- Focus on: structure and relationships only

## Output Requirements
- Include EVERY collection/table in the codebase
- Include EVERY field on each collection
- Keep descriptions short and clear (1 sentence)
- Use simple relationship terms anyone can understand

## Example Output Structure

```json
{
  "overview": "This is an e-commerce application's data model. It manages products, user accounts, shopping carts, and orders. The main collections are Users (authentication), Products (catalog), Carts (active shopping), and Orders (purchase history).",
  "framework": "Express + Mongoose",
  "database": "MongoDB",
  "collections": [
    {
      "name": "Users",
      "type": "collection",
      "purpose": "Stores user account and authentication information",
      "fields": [
        {
          "name": "_id",
          "data_type": "string",
          "required": true,
          "description": "Unique user identifier"
        },
        {
          "name": "email",
          "data_type": "string",
          "required": true,
          "description": "User's email for login"
        },
        {
          "name": "name",
          "data_type": "string",
          "required": true
        },
        {
          "name": "createdAt",
          "data_type": "date",
          "required": true
        }
      ],
      "relationships": [
        {
          "related_to": "Orders",
          "relationship_type": "one-to-many",
          "description": "A user can have multiple orders"
        },
        {
          "related_to": "Carts",
          "relationship_type": "one-to-one",
          "description": "Each user has one active shopping cart"
        }
      ]
    },
    {
      "name": "Products",
      "type": "collection",
      "purpose": "Stores product catalog information",
      "fields": [
        {
          "name": "_id",
          "data_type": "string",
          "required": true
        },
        {
          "name": "name",
          "data_type": "string",
          "required": true
        },
        {
          "name": "price",
          "data_type": "number",
          "required": true
        },
        {
          "name": "stock",
          "data_type": "number",
          "required": true
        },
        {
          "name": "category",
          "data_type": "string",
          "required": false
        }
      ],
      "relationships": [
        {
          "related_to": "Orders",
          "relationship_type": "many-to-many",
          "description": "Products can appear in multiple orders"
        }
      ]
    }
  ]
}
```

## Quality Checklist
Before submitting, verify:
- [ ] Overview explains what this data model is for
- [ ] All collections/tables are documented
- [ ] Every field on each collection is included
- [ ] Relationships between collections are clear
- [ ] Descriptions are concise and helpful
"""

data_model_prompt = {
    "name": "data_model",
    "description": "Analyzes and documents a codebase's complete data model structure",
    "prompt_template": prompt_template,
    "schema": DataModel,
}