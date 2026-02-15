# ChongMing Backend Architecture

## Layer Diagram

```
┌─────────────────────────────────────────────┐
│  Presentation:   app.api                    │  ← HTTP endpoints
├─────────────────────────────────────────────┤
│  Orchestration:  app.tasks, app.worker      │  ← Celery tasks
├─────────────────────────────────────────────┤
│  Business Logic: app.services               │  ← Domain logic
├─────────────────────────────────────────────┤
│  Implementation: app.engines, app.agents    │  ← Execution engines
├─────────────────────────────────────────────┤
│  Data:           app.models, app.schemas    │  ← ORM & Pydantic
├─────────────────────────────────────────────┤
│  Infrastructure: app.core, app.utils        │  ← Config, DB, AI client
└─────────────────────────────────────────────┘
```

## Dependency Rules

Imports flow **top-down only**. A module may import from any layer at or below its own level, but **never** from above.

| Source Layer     | Allowed Targets                                    |
|------------------|----------------------------------------------------|
| `app.api`        | `app.services`, `app.tasks`, `app.core`, `app.schemas` |
| `app.tasks`      | `app.services`, `app.engines`, `app.core`, `app.models` |
| `app.services`   | `app.engines`, `app.core`, `app.models`, `app.schemas`  |
| `app.engines`    | `app.core`, `app.models`, `app.schemas`            |
| `app.core`       | `app.utils` only                                   |

### Special Rules

- **`app.api` must NOT import** `app.engines` or `app.models` directly. Use service methods.
- **`app.engines` must NOT import** `app.agents`. Agents consume engines, not vice versa.
- **`app.core` must NOT import** `app.services`. Use Dependency Inversion (Protocol + DI).

### Documented Exceptions

| Exception | Reason |
|-----------|--------|
| `services.phoenix.visual_comparator` → `engines.vision.omni_client` | Future AI-VRT feature; OmniClient calls are currently commented out. |

## Enforcement

Architecture rules are enforced via `import-linter`:

```bash
# Install
pip install import-linter

# Run checks
cd backend
lint-imports
```

The rules are defined in `.importlinter` at the project root.

## Key Design Patterns

### Dependency Inversion (Core ↔ Services)

`AIClientManager` in `core` depends on an abstract `AIConfigProvider` protocol, **not** on the concrete `AIConfigService`.

```
app.core.ai_config_provider   →  AIConfigProvider (Protocol)
app.core.ai_client             →  AIClientManager (uses Protocol)
app.services.smart_ops         →  AIConfigProviderImpl (implements Protocol)
app.main                       →  Wires impl into manager at startup
```

### Service Layer Encapsulation (API ↔ Models)

API endpoints do **not** access ORM models directly. Instead, services expose `*_dict()` methods that return plain dictionaries.

```
app.api.endpoints.executions   →  calls ExecutionService.get_execution_status_dict()
app.services.execution_service →  queries Execution model, returns dict
```
