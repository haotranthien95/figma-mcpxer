# Phase 2: Solution Design

Plan the architecture and technical approach before writing a single line of code.

## Objective

- Choose the right architecture pattern for the task
- Define all modules, files, and data models to create/modify
- Map external service integrations (LLM, MCP, Figma, DB)
- Produce a design plan that another developer could implement

## Input

- Dependency: `context-report.json` (from Phase 1)
- Template: `templates/python-service.md`

## Execution Steps

### Step 1: Read Context

```javascript
const context = JSON.parse(Read(`${workDir}/context-report.json`));
```

### Step 2: Choose Architecture Pattern

Select the right pattern based on task type:

```javascript
const PATTERNS = {
  // REST API with business logic and DB
  "api_service": {
    layers: ["api/v1/", "services/", "repositories/", "models/", "schemas/"],
    framework: "FastAPI + SQLAlchemy 2 async"
  },
  // MCP server exposing tools to LLM
  "mcp_server": {
    structure: ["mcp_server.py", "tools/", "config.py"],
    framework: "mcp Python SDK"
  },
  // AI agent with tool use
  "llm_agent": {
    structure: ["agent.py", "tools/", "prompts/", "memory/"],
    framework: "Anthropic SDK + custom tools"
  },
  // Background worker / task queue
  "worker": {
    layers: ["workers/", "tasks/", "services/"],
    framework: "Celery or asyncio tasks"
  },
  // CLI tool / script
  "cli": {
    structure: ["cli.py", "commands/", "utils/"],
    framework: "Typer or argparse"
  }
};

// Recommendation logic
const selectedPattern = context.framework.includes("fastapi") ? "api_service"
  : context.external_integrations.mcp === "yes" ? "mcp_server"
  : context.external_integrations.llm === "yes" ? "llm_agent"
  : "api_service";  // default
```

### Step 3: Define Data Models

```javascript
// Write out Pydantic schemas and SQLAlchemy models
const dataModels = {
  pydantic_schemas: [
    // { name, fields, purpose }
  ],
  sqlalchemy_models: [
    // { table_name, columns, relationships }
  ]
};
```

### Step 4: Define API Contract (if applicable)

```javascript
const apiContract = [
  // { method, path, request_body, response, auth_required, description }
  { method: "POST", path: "/v1/items", request_body: "ItemCreate", response: "ItemResponse", auth_required: true },
  { method: "GET", path: "/v1/items/{id}", request_body: null, response: "ItemResponse", auth_required: true },
];
```

### Step 5: Plan File Changes

```javascript
const filePlan = {
  create: [
    // List all new files with 1-line purpose
    { path: "src/models/item.py", purpose: "SQLAlchemy Item model" },
    { path: "src/schemas/item.py", purpose: "Pydantic schemas for Item CRUD" },
    { path: "src/services/item_service.py", purpose: "Item business logic" },
    { path: "src/repositories/item_repository.py", purpose: "DB queries for items" },
    { path: "src/api/v1/items.py", purpose: "FastAPI router for /items" },
    { path: "tests/unit/test_item_service.py", purpose: "Unit tests for item logic" },
    { path: "tests/integration/test_items_api.py", purpose: "Integration tests for /items endpoint" },
  ],
  modify: [
    { path: "src/main.py", change: "Register new items router" },
    { path: "src/models/__init__.py", change: "Export Item model" },
  ]
};
```

### Step 6: Write Design Plan

```javascript
const designPlan = `# Solution Design

## Approach
${selectedPatternDescription}

## Architecture
${architectureDiagram}

## Data Models
${dataModelsSummary}

## API Contract
${apiContractTable}

## Files to Create
${filePlan.create.map(f => `- \`${f.path}\` — ${f.purpose}`).join('\n')}

## Files to Modify
${filePlan.modify.map(f => `- \`${f.path}\` — ${f.change}`).join('\n')}

## External Integrations
${integrationsDescription}

## Open Questions
- None (or list anything that blocks implementation)
`;

Write(`${workDir}/design-plan.md`, designPlan);
```

## Output

- **File**: `design-plan.md`
- **Format**: Markdown

## Quality Checklist

- [ ] Pattern choice is justified (not just default)
- [ ] All files are listed with a clear purpose
- [ ] Data models are defined (not vague)
- [ ] API contract is explicit (paths, methods, schemas)
- [ ] No ambiguities remain before coding starts
- [ ] Design respects existing codebase patterns (from context-report.json)

## Next Phase

→ [Phase 3: Implementation](03-implementation.md)
