# Type Definition Schema

A type definition is a markdown file that describes a document type. `document-define` reads this file and generates a complete skill for managing documents of that type.

## Location

Type definitions live at `.config/documents/types/{name}.md` in the consuming project.

## Format

```markdown
# {Display Name}

## Identity
- name: {slug} — lowercase, hyphenated, used as `type:` value in frontmatter
- display: {Display Name} — human-readable name
- description: {one-line description}

## Fields

### Required
- `type: string` — always "{type-name}". This field is mandatory on every type.
- `{field}: {type}` — {description}

### Optional
- `{field}: {type}` — {description}

Field types: string, date (YYYY-MM-DD), enum({values}), link (markdown link), links (markdown links list), boolean, number

## Sections

### Required
- `## {Section Name}` — {description of expected content}

### Optional
- `## {Section Name}` — {description of expected content}

## Relationships (optional)
- links-to: {type} via {field} — {cardinality: one|many} — {description}
- linked-from: {type} via {field} — {description of how other types reference this one}

Omit this section entirely if the type has no relationships.

## Lifecycle (optional)
- status-field: {field name, typically `status`}
- values: {comma-separated valid statuses}
- transitions:
  - {from} -> {to} — {condition or description}
  - {from} -> {to}

Omit this section if the type has no lifecycle (e.g., meeting notes are informational with no status transitions). When present, the status field must be declared in Fields.

## Creation
- mode: {template|conversational|reverse}
- template-sections: {which sections to pre-fill vs leave empty}
- template-designed-by: {avatar names or "auto"} — (optional) which expert agents designed the template. Use `/consult` or `/review` with these avatars to refine the template. A team of agents may collaborate.
- conversational-phases: {ordered list of what to gather}
  - {phase}: {what it covers}
- reverse-source: {what artifact type to reverse-engineer from, e.g., "Figma design", "existing document"}

The template is the contract between expert agents and the document skill. Expert agents design the template (sections, inline guidance comments, structure). The document skill stores and enforces it. When an expert agent creates an instance, the template's sections match the agent's expectations. Users can always deviate.

## Collections (optional)

Declares child collections this type hosts within its directory. Each row describes a collection of another type, keyed by a field, at a relative path from the parent document's directory.

| Collection | Type | Key | Path |
|------------|------|-----|------|
| stories | user-story | story-id | ./stories/{story-id}.md |

- **Collection**: display name for the collection
- **Type**: the child document type (must match a type definition name)
- **Key**: the field in the child type used as the filename/identifier
- **Path**: relative path from the parent document's directory

The parent type owns the collection declaration. Child types do NOT reference the parent. When a parent document is created, its declared collection directories are scaffolded. To resolve where a child document lives, traverse: Root → find all types whose Collections table includes this child type → use the matching path pattern.

A type can live in multiple places. The same type definition can appear in the root type's Collections AND in a parent type's Collections. Different instances of the type live at different paths. When creating, the skill asks the user which location to use. For example, an initiative could live at `./Initiatives/{name}.md` (root) or at `./Programs/{name}/initiatives/{name}.md` (under a program). Both are valid.

## Facets (optional)

Declares sections that can be promoted to sibling files when the hub document exceeds the file size limit (150 lines). Each row maps a section heading to a sibling file and its document type.

| Section | File | Type |
|---------|------|------|
| Strategy | ./strategy.md | strategic-context |

- **Section**: the H2 heading in the hub document
- **File**: relative path for the extracted file
- **Type**: the document type of the extracted file (must match a type definition)

When a facet is inline, the section content lives in the hub document. When extracted, the section is replaced with a link: `See [Section](./file.md)`.

When a type appears in both a parent's Facets table AND its Collections table, the Facets path takes precedence for that specific relationship.
```

## Example: Brand Type Definition

```markdown
# Brand

## Identity
- name: brand
- display: Brand
- description: A brand identity within the organization

## Fields

### Required
- `type: string` — always "brand"
- `name: string` — brand name
- `created: date` — creation date

### Optional
- `description: string` — one-line summary
- `region: string` — primary market or region
- `products: links` — associated products

## Sections

### Required
- `## Overview` — brand description and positioning

### Optional
- `## Voice` — brand voice characteristics
- `## Identity` — visual identity guidelines
- `## Guidelines` — usage guidelines

## Relationships
- linked-from: product via brand — products reference this brand

## Lifecycle
- status-field: status
- values: draft, active, archived
- transitions:
  - draft -> active — brand is ready for use
  - active -> archived — brand is retired

## Creation
- mode: template
- template-sections: Overview (prompt user), Voice (leave empty), Identity (leave empty), Guidelines (leave empty)
```

## Example: Product Type Definition (with Collections and Facets)

```markdown
# Product

## Identity
- name: product
- display: Product
- description: A product hub with child collections and extractable facets

## Fields

### Required
- `type: string` — always "product"
- `name: string` — product name
- `status: enum(active, sunset, planned, discovery)` — lifecycle stage
- `created: date` — creation date

### Optional
- `description: string` — one-line summary
- `brand: link` — link to parent brand
- `owner: string` — product owner

## Sections

### Required
- `## Overview` — product description and goals

### Optional
- `## Goals` — product objectives
- `## Team` — people involved

## Relationships
- links-to: brand via brand — one — parent brand
- linked-from: prd via product — PRDs reference this product

## Collections
| Collection | Type | Key | Path |
|------------|------|-----|------|
| stories | user-story | story-id | ./stories/{story-id}.md |
| opportunities | opportunity-tree | name | ./opportunities/{name}.md |
| experiments | experiment | name | ./experiments/{name}.md |

## Facets
| Section | File | Type |
|---------|------|------|
| Strategy | ./strategy.md | strategic-context |
| Product Requirements | ./prd.md | prd |

## Lifecycle
- status-field: status
- values: discovery, planned, active, sunset
- transitions:
  - discovery -> planned — problem validated
  - planned -> active — development started
  - active -> sunset — product being retired

## Creation
- mode: template
- template-sections: Overview (prompt user), Goals (leave empty), Team (leave empty)
```

## Example: PRD Type Definition (hosted by product via Facets)

```markdown
# PRD

## Identity
- name: prd
- display: PRD
- description: Product Requirements Document

## Fields

### Required
- `type: string` — always "prd"
- `product: link` — link to parent product hub
- `status: enum(draft, review, approved, shipped)` — lifecycle stage
- `created: date` — creation date
- `author: string` — document author

### Optional
- `description: string` — one-line summary
- `depends-on: links` — dependencies on other documents
- `jira: string` — Jira ticket or epic key

## Sections

### Required
- `## Problem Statement` — what problem this solves
- `## Context` — relevant background
- `## Desired Outcome` — what success looks like
- `## Success Metrics` — how to measure success

### Optional
- `## Executive Summary` — brief overview for stakeholders
- `## User Stories` — user-facing requirements
- `## Product Scope` — what's in and out of scope
- `## Functional Requirements` — detailed requirements
- `## Non-Functional Requirements` — performance, security, etc.
- `## Design Considerations` — UX and design constraints
- `## Technical Constraints` — technical limitations
- `## Open Questions` — unresolved items

## Relationships
- links-to: product via product — one — parent product
- linked-from: user-story via prd — stories reference this PRD

## Lifecycle
- status-field: status
- values: draft, review, approved, shipped
- transitions:
  - draft -> review — ready for stakeholder review
  - review -> draft — needs revisions
  - review -> approved — stakeholders approve
  - approved -> shipped — feature shipped

## Creation
- mode: conversational
- conversational-phases:
  - problem: What problem are we solving? Who has this problem?
  - context: What's the current state? What's been tried?
  - outcome: What does success look like? How will we measure it?
  - scope: What's in scope? What's explicitly out?
  - requirements: Functional and non-functional requirements
  - review: Review the full PRD, offer revisions
- reverse-source: Figma design, existing prototype, competitor product
```

## Path Conventions

- Directory names follow the project's conventions (typically kebab-case or PascalCase as configured in root.md Conventions).
- Path patterns use `{field-name}` placeholders that resolve to the document's frontmatter values.
- Compound keys (e.g., `{category}/{name}`) use multiple fields from the document's frontmatter to build the path. Each placeholder maps to one field.
- The Key column in Collections tables identifies which field(s) generate the filename. For compound paths, use hyphenated field names (e.g., `category-name` means fields `category` and `name`).

## Design Principles

1. **Type definitions describe shape, not location.** They describe what a type IS (fields, sections, relationships, lifecycle). Where it lives is declared by whoever hosts it (root type or parent type).
2. **One file per type.** The type definition is the single source of truth for document shape. Generated skills reference it via source header.
3. **Human-readable.** Type definitions are markdown, not YAML or JSON. Anyone can read and edit them.
4. **Additive.** New fields in the schema don't break existing type definitions. Older definitions generate simpler skills.
5. **Relationship declarations are one-sided.** Each type declares what it links TO. `linked-from` is informational, not enforced.
6. **Types can live in multiple places.** The same type definition can be hosted by different parents. Each instance lives at the path declared by its hosting parent. The type definition is reusable across hosts.
7. **Location flows top-down.** Root type → Collections → child types → their Collections. No type declares its own location. No child references its parent.
