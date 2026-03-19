# Phase 1: Context Analysis

Understand the full scope of the task, the existing codebase, and any constraints before designing a solution.

## Objective

- Identify exactly what needs to be built or fixed
- Map the existing codebase structure and conventions
- Detect the tech stack and dependencies
- Surface constraints (performance, team patterns, existing integrations)

## Input

- Dependency: User task description (natural language)
- Config: `{workDir}/skill-config.json` (if resuming)

## Execution Steps

### Step 1: Understand the Task

```javascript
// Clarify scope if the task is ambiguous
const taskDescription = userMessage;

// Ask clarifying questions only if critical info is missing:
// - What is the expected input/output?
// - Is there an existing pattern to follow?
// - Any hard constraints (performance, backwards compat)?
```

### Step 2: Explore the Codebase

```javascript
// Detect project type
const pyprojectExists = Glob("pyproject.toml");
const requirementsExists = Glob("requirements*.txt");
const dockerfileExists = Glob("Dockerfile");

// Read key config files
if (pyprojectExists.length) {
  const pyproject = Read("pyproject.toml");
  // Extract: python version, dependencies, dev tools (ruff, mypy, pytest)
}

// Map source structure
const sourceFiles = Glob("src/**/*.py");
const testFiles = Glob("tests/**/*.py");

// Read entry points and core modules
const mainFile = Read("src/main.py");  // or app.py, __init__.py
```

### Step 3: Identify Existing Patterns

```javascript
// Look for established conventions
const existingRouters = Glob("src/api/**/*.py");
const existingServices = Glob("src/services/**/*.py");
const existingModels = Glob("src/models/**/*.py");

// Read 1-2 examples to understand naming, patterns
if (existingServices.length) {
  const sampleService = Read(existingServices[0]);
  // Note: async/sync style, error handling approach, DI pattern
}
```

### Step 4: Detect External Integrations

```javascript
// Check for existing LLM / MCP usage
const llmUsage = Grep("anthropic|openai|litellm", { glob: "src/**/*.py" });
const mcpUsage = Grep("mcp.server|mcp.client", { glob: "src/**/*.py" });
const figmaUsage = Grep("figma", { glob: "src/**/*.py", "-i": true });

// Check docker-compose for service dependencies
const dockerCompose = Glob("docker-compose*.yml");
if (dockerCompose.length) {
  const compose = Read(dockerCompose[0]);
  // Note: DB type, message queues, caches
}
```

### Step 5: Write Context Report

```javascript
const contextReport = {
  task: taskDescription,
  python_version: detectedPythonVersion,
  framework: detectedFramework,  // fastapi, flask, django, plain
  key_dependencies: detectedDeps,
  existing_patterns: {
    async_style: true,  // or false
    error_handling: "custom exceptions + global handler",  // or whatever detected
    di_pattern: "FastAPI Depends"
  },
  external_integrations: {
    llm: llmUsage.length > 0 ? "yes" : "no",
    mcp: mcpUsage.length > 0 ? "yes" : "no",
    figma: figmaUsage.length > 0 ? "yes" : "no"
  },
  constraints: [],  // populated from task description or user input
  files_to_create: [],  // to be filled in Phase 2
  files_to_modify: []   // to be filled in Phase 2
};

Write(`${workDir}/context-report.json`, JSON.stringify(contextReport, null, 2));
```

## Output

- **File**: `context-report.json`
- **Format**: JSON

## Quality Checklist

- [ ] Task is understood well enough to write a design plan without guessing
- [ ] Existing patterns are documented (not assumed)
- [ ] External services are identified
- [ ] No ambiguities remain that would block Phase 2

## Next Phase

→ [Phase 2: Solution Design](02-solution-design.md)
