# AI Agent Development Standards and Best Practices

## Overview

This document outlines the standards, conventions, and best practices that all AI agents must follow when working on the **DW AI Cloud FinOps** project. Adherence to these guidelines ensures consistency, maintainability, and quality across all sub-projects.

## Technology Stack

All sub-projects in this repository **must** be developed using:

- **Language**: TypeScript (strict mode enabled)
- **Runtime**: Node.js (LTS)
- **Backend Framework**: NestJS
- **ORM**: TypeORM
- **Testing**: Jest (with `@nestjs/testing`)
- **Database Schema**: `finops` (all tables under the `finops` PostgreSQL schema)
- **Package Manager**: npm (use `package-lock.json` for reproducible builds)
- **Containerization**: Docker Compose (PostgreSQL + all services)
- **Linting**: ESLint with `@typescript-eslint`
- **Formatting**: Prettier
- **AI Agent Framework**: TBD (to be decided)

## Project Structure

This is a monorepo containing the following sub-projects:

```
cloud-finops/
├── azure-consumption-extractor/   # Azure Cost Management API integration
├── azure-metrics-extractor/       # Azure resource usage metrics
├── dashboard/                     # Frontend visualization and reporting
├── database/                      # Shared database schemas and migrations
├── ai-agents/                     # AI-powered analysis agents
└── .ai/                           # AI agent configuration
```

### Sub-Project Layout (NestJS)

Each backend sub-project must follow this structure:

```
<project>/
├── src/
│   ├── main.ts                    # Application entry point
│   ├── app.module.ts              # Root module
│   ├── config/                    # Configuration (env validation, constants)
│   ├── common/                    # Shared utilities, decorators, filters
│   │   ├── decorators/
│   │   ├── filters/
│   │   ├── guards/
│   │   ├── interceptors/
│   │   ├── pipes/
│   │   └── interfaces/
│   └── modules/
│       └── <feature>/
│           ├── <feature>.module.ts
│           ├── <feature>.controller.ts
│           ├── <feature>.service.ts
│           ├── dto/
│           │   ├── create-<feature>.dto.ts
│           │   └── update-<feature>.dto.ts
│           ├── entities/
│           │   └── <feature>.entity.ts
│           └── <feature>.service.spec.ts
├── tests/                         # E2E and integration tests
│   └── <feature>.e2e-spec.ts
├── config/                        # Environment-specific configs
├── docs/                          # Project documentation
├── tsconfig.json
├── tsconfig.build.json
├── .eslintrc.js
├── .prettierrc
├── nest-cli.json
└── package.json
```

## Code Style and Formatting

### General Principles

- Write clean, readable, and self-documenting code
- Follow the DRY (Don't Repeat Yourself) principle
- Follow the KISS (Keep It Simple, Stupid) principle
- Follow SOLID principles, especially in NestJS services
- Maintain consistent indentation: **2 spaces** (no tabs)
- Keep line length under 100 characters where practical
- Use meaningful variable and function names that convey intent
- Prefer immutability (`const` over `let`, `readonly` properties)
- Avoid `any` — use proper types, generics, or `unknown`

### TypeScript Configuration

All projects must enable strict mode in `tsconfig.json`:

```json
{
  "compilerOptions": {
    "strict": true,
    "strictNullChecks": true,
    "strictPropertyInitialization": true,
    "noImplicitAny": true,
    "noImplicitReturns": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "esModuleInterop": true,
    "emitDecoratorMetadata": true,
    "experimentalDecorators": true,
    "resolveJsonModule": true,
    "declaration": true,
    "target": "ES2022",
    "module": "commonjs",
    "moduleResolution": "node"
  }
}
```

### Naming Conventions

- **Variables and functions**: `camelCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Classes, Interfaces, Types, Enums**: `PascalCase`
- **Interfaces**: Do NOT prefix with `I` — use descriptive names (e.g., `ConsumptionRecord`, not `IConsumptionRecord`)
- **Type aliases**: `PascalCase` (e.g., `type ResourceMetric = { ... }`)
- **Enums**: `PascalCase` for enum name, `PascalCase` for members
- **Private class members**: Use TypeScript `private` keyword (no underscore prefix)
- **Protected class members**: Use TypeScript `protected` keyword
- **Boolean variables**: Use prefixes like `is`, `has`, `should`, `can`
- **Files**: `kebab-case` (e.g., `consumption-record.entity.ts`, `azure-cost.service.ts`)
- **NestJS files**: Follow the pattern `<name>.<type>.ts` (e.g., `cost.controller.ts`, `cost.service.ts`, `cost.module.ts`)
- **DTOs**: `Create<Feature>Dto`, `Update<Feature>Dto`, `<Feature>ResponseDto`
- **Entities**: Singular noun matching the table (e.g., `ConsumptionRecord`)

### ESLint and Prettier

Every sub-project must include ESLint and Prettier configuration:

- Use `@typescript-eslint/recommended` rules as baseline
- Enable `no-explicit-any` as an error
- Enable `explicit-function-return-type` for public methods
- Prettier config: single quotes, trailing commas, 2-space indent, 100 print width
- Run `npm run lint` and `npm run format` before every commit

## TypeScript Best Practices

### Type Safety

- Always define explicit return types for public functions and methods
- Use `interface` for object shapes that may be extended; use `type` for unions, intersections, and mapped types
- Prefer `unknown` over `any` when the type is truly unknown
- Use discriminated unions for complex state management
- Leverage `Readonly<T>`, `Partial<T>`, `Pick<T>`, `Omit<T>` utility types
- Use `as const` for literal type assertions when appropriate
- Define enums for fixed sets of values; prefer string enums for readability

### Generics

- Use generics to build reusable, type-safe abstractions
- Provide meaningful constraint names (e.g., `<TEntity extends BaseEntity>`)
- Avoid overly complex generic signatures — simplicity wins

### Imports and Exports

- Use barrel exports (`index.ts`) for public module APIs
- Prefer named exports over default exports
- Organize imports: Node built-ins → external packages → internal modules
- Use path aliases (`@modules/`, `@common/`, `@config/`) via `tsconfig.json` paths

## NestJS Best Practices

### Architecture

- Follow NestJS modular architecture strictly
- Each feature domain must have its own module
- Use dependency injection everywhere — never instantiate services manually
- Keep controllers thin: validate input, delegate to services, return responses
- Business logic belongs in services, not controllers or entities

### Modules

- Register all providers, controllers, imports, and exports explicitly
- Use `forRoot()` / `forRootAsync()` for dynamic module configuration
- Use `ConfigModule` with validation (via `class-validator` and `class-transformer`) for env vars
- Avoid circular dependencies between modules

### Controllers

- Use proper HTTP decorators (`@Get`, `@Post`, `@Put`, `@Patch`, `@Delete`)
- Apply validation pipes to all input (`@UsePipes(new ValidationPipe())`)
- Use DTOs for all request bodies and query parameters
- Return consistent response shapes
- Use `@HttpCode()` where the default status code is not appropriate

### Services

- Services must be `@Injectable()` and registered in their module's providers
- Use constructor injection for all dependencies
- Implement proper error handling with NestJS built-in exceptions (`NotFoundException`, `BadRequestException`, etc.)
- Keep services focused on a single responsibility

### DTOs and Validation

- Use `class-validator` decorators on all DTO properties
- Use `class-transformer` for type transformation
- Create separate DTOs for create, update, and response operations
- Use `PartialType()`, `PickType()`, `OmitType()` from `@nestjs/mapped-types`

### Guards, Pipes, Interceptors, and Filters

- Use guards for authentication and authorization logic
- Use pipes for data validation and transformation
- Use interceptors for logging, response mapping, and caching
- Use exception filters for consistent error response formatting
- Prefer global registration for cross-cutting concerns

## TypeORM Best Practices

### Entities

- Define entities using TypeORM decorators (`@Entity`, `@Column`, `@PrimaryGeneratedColumn`, etc.)
- Use `uuid` for primary keys where appropriate
- Always define `@CreateDateColumn()` and `@UpdateDateColumn()` on entities
- Define relations explicitly (`@OneToMany`, `@ManyToOne`, `@ManyToMany`, `@OneToOne`)
- Set `eager: false` on relations by default; load explicitly when needed
- Use column types that match the target database precisely

### Repositories

- Use the Repository pattern via TypeORM's `@InjectRepository()`
- Create custom repository methods for complex queries
- Use QueryBuilder for complex joins and aggregations
- Never execute raw SQL unless absolutely necessary (and document why)

### Migrations

- **Always** use TypeORM migrations for schema changes — never use `synchronize: true` in production
- Name migrations descriptively (e.g., `1711234567890-AddConsumptionTable`)
- Keep migrations reversible (implement both `up()` and `down()`)
- Store migrations in `database/migrations/`
- Test migrations against a clean database before committing

### Transactions

- Use transactions for operations that modify multiple entities
- Use TypeORM's `DataSource.transaction()` or `QueryRunner` for transaction management
- Always handle transaction rollback in error scenarios

## Documentation Requirements

### Code Comments

- Document all public APIs, functions, and classes using **TSDoc** format (`/** ... */`)
- Include `@param`, `@returns`, `@throws`, and `@example` tags
- Explain "why" not "what" — code should be self-explanatory for "what"
- Update comments when code changes
- Do NOT leave commented-out code in the codebase

### README and Documentation

- Maintain up-to-date `README.md` in each sub-project with setup instructions
- Document all environment variables and configuration options
- Include API documentation (use Swagger/OpenAPI via `@nestjs/swagger`)
- Provide usage examples and common scenarios
- Document database schema and entity relationships

### API Documentation

- Use `@nestjs/swagger` decorators on all controllers and DTOs
- Document all endpoints with `@ApiOperation`, `@ApiResponse`, `@ApiTags`
- Expose Swagger UI at `/api/docs` in development
- Keep API docs in sync with actual implementation

## Testing Standards

### Verification Requirements

- **ALWAYS verify code is running and working before marking tasks as complete**
- Run `npm run build` to verify compilation succeeds with no errors
- Run `npm run test` to verify all unit tests pass
- Run `npm run test:e2e` to verify integration tests pass
- Run `npm run lint` to verify no linting errors
- Ensure services start successfully (`npm run start:dev`) and respond to basic operations
- Verify configuration files are correct and complete

### Test Coverage

- Maintain minimum **80% code coverage**
- Write unit tests for all services and utility functions
- Write e2e tests for all API endpoints
- Include integration tests for database operations
- Test edge cases and error conditions
- Use `npm run test:cov` to check coverage

### Test Structure

- Follow **Arrange-Act-Assert (AAA)** pattern
- Use descriptive test names: `it('should return 404 when record is not found')`
- Keep tests isolated and independent
- Use NestJS `Test.createTestingModule()` for unit tests
- Mock external dependencies using Jest mocks or NestJS `overrideProvider()`
- Use in-memory databases (SQLite) or test containers for integration tests
- Place unit tests next to the source file (`*.spec.ts`)
- Place e2e tests in the `tests/` directory (`*.e2e-spec.ts`)

### Jest Configuration

- Use `ts-jest` for TypeScript support
- Configure module path aliases matching `tsconfig.json`
- Enable coverage collection with thresholds enforced

## Error Handling

### NestJS Exception Handling

- Use NestJS built-in HTTP exceptions (`NotFoundException`, `BadRequestException`, `UnauthorizedException`, etc.)
- Create custom exceptions extending `HttpException` for domain-specific errors
- Implement a global exception filter for consistent error response formatting
- Always return structured error responses:
  ```json
  {
    "statusCode": 404,
    "message": "Consumption record not found",
    "error": "Not Found",
    "timestamp": "2026-03-25T12:00:00.000Z"
  }
  ```

### General Error Handling

- Use `try-catch` blocks for async operations that may fail
- Provide meaningful error messages with relevant context
- Log errors with appropriate context (request ID, user, operation)
- Fail fast and fail explicitly
- Never swallow exceptions silently

### Logging

- Use NestJS built-in `Logger` or integrate with `winston`/`pino`
- Use appropriate log levels: `debug`, `log`, `warn`, `error`, `verbose`
- Include relevant context in log messages (correlation IDs, operation names)
- Never log sensitive information (API keys, tokens, passwords)
- Structure logs as JSON for easy parsing and searching

## Security Practices

### Sensitive Data

- Never commit secrets, API keys, or credentials to the repository
- Use environment variables for all configuration (via `@nestjs/config`)
- Add `.env` files to `.gitignore`
- Provide a `.env.example` file with placeholder values
- Implement proper input validation using `class-validator` on all DTOs
- Use `helmet` middleware for HTTP security headers
- Enable CORS only for allowed origins

### Authentication and Authorization

- Use NestJS guards for auth logic
- Implement role-based access control where needed
- Validate all tokens and credentials server-side
- Follow the principle of least privilege

### Dependencies

- Keep dependencies up to date (`npm outdated`, `npm audit`)
- Audit dependencies for security vulnerabilities regularly
- Use `package-lock.json` to ensure reproducible builds
- Remove unused dependencies
- Pin major versions to avoid unexpected breaking changes

## Version Control

### Commit Messages

- Use conventional commit format: `type(scope): description`
- Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `ci`
- Scope should reference the sub-project or module (e.g., `feat(consumption): add daily aggregation endpoint`)
- Keep subject line under 72 characters
- Include detailed description in commit body when needed

### Branch Strategy

- Use feature branches for new development
- Branch naming: `feature/<scope>-<description>`, `bugfix/<scope>-<description>`, `hotfix/<description>`, `refactor/<scope>-<description>`
- Keep branches short-lived and focused
- Rebase before merging to maintain clean history
- Delete branches after merging

## Performance Considerations

### Optimization

- Profile before optimizing — use data, not assumptions
- Avoid premature optimization
- Consider time and space complexity
- Use appropriate data structures (Maps, Sets, etc.)
- Implement caching where beneficial (use `@nestjs/cache-manager`)
- Use pagination for list endpoints (offset/limit or cursor-based)

### Database Performance

- Add proper indexes to frequently queried columns
- Use `select` option in TypeORM queries to fetch only needed columns
- Avoid N+1 query problems — use `leftJoinAndSelect` or `relations` explicitly
- Use QueryBuilder for complex aggregations instead of loading full entities
- Monitor and log slow queries

### Resource Management

- Close resources properly (database connections, streams, file handles)
- Use TypeORM connection pooling (configured via `DataSource` options)
- Monitor memory usage and prevent leaks
- Use `async/await` for all I/O operations — never block the event loop
- Implement proper graceful shutdown (`app.enableShutdownHooks()`)

## Continuous Integration / Deployment

### CI Pipeline

- All tests must pass before merging
- ESLint and Prettier checks must pass
- TypeScript compilation must succeed with no errors and no warnings
- Code coverage thresholds must be met
- Build Docker images for each service

### Deployment

- Use automated deployment pipelines
- Implement proper rollback strategies
- Run database migrations as part of the deployment process
- Monitor deployments for issues
- Maintain deployment documentation
- Use environment-specific configuration (dev, staging, production)

## AI-Specific Guidelines

### Code Generation

- **CRITICAL: Always test and verify code works before marking tasks complete**
- Run services, execute tests, and verify functionality manually
- Run `npm run build` and `npm run lint` before considering any task done
- Verify generated code follows all standards in this document
- Review generated code for potential security issues
- Never generate code with `any` types — find the correct type

### Context Awareness

- Understand existing codebase patterns before making changes
- Maintain consistency with existing code style and architecture
- Consider the NestJS module dependency graph when adding features
- Respect established conventions in each sub-project
- Check for existing utilities and shared code before creating new ones

### Documentation Maintenance (Mandatory)

Updating project documentation is a **mandatory step** between completing a task and starting the next one. This is not optional — it ensures the project state is always accurately represented.

**After completing every task, before starting the next one:**

1. **Update `TASKS.md`** — Mark the completed task as `DONE`, check all acceptance criteria, add notes with verification results. Unblock downstream tasks whose blockers are now resolved.
2. **Update `CLAUDE.md`** — If the task introduced new patterns, conventions, dependencies, or architectural decisions, document them here.
3. **Update `README.md`** — If the task changed setup steps, prerequisites, environment variables, services, or project structure, update the root README accordingly.
4. **Update sub-project READMEs** — If a sub-project gained new features, modules, or configuration, update its own README.
5. **Review consistency** — Ensure all docs agree on: project structure, tech stack, environment variables, service ports, and database schema.

**This is a standard practice, not a suggestion.** Treat documentation updates as part of the definition of done for every task.

### Task Execution

- Break complex tasks into smaller, verifiable steps
- Commit working increments — never commit broken code
- Update tests when changing behavior
- Update documentation when changing APIs or configuration
- Acknowledge when uncertain about requirements and ask clarifying questions
- Suggest alternatives when appropriate
- Highlight potential issues, trade-offs, or concerns proactively

## Compliance and Legal

### Licensing

- Respect open-source licenses
- Do not copy code without proper attribution
- Ensure compatibility with project license
- Document third-party code usage

### Copyright

- Do not violate copyright laws
- Use properly licensed resources
- Attribute sources appropriately

## Maintenance and Technical Debt

### Code Quality

- Refactor code when improving functionality
- Address TODO comments promptly — include a ticket/issue reference in TODOs
- Track and prioritize technical debt
- Remove dead code and unused imports

### Deprecation

- Mark deprecated code clearly with `@deprecated` TSDoc tag
- Provide migration paths for deprecated APIs
- Set removal timelines
- Update documentation accordingly

---

**Note**: These standards are living documents and should be updated as the project evolves and new best practices emerge. All team members and AI agents are expected to follow these guidelines and suggest improvements when appropriate.