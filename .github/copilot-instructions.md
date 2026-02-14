# Copilot Instructions

This document outlines the available skills and best practices for developing the simulation-app backend. The backend is built with FastAPI and follows clean architecture principles.

## Table of Contents

1. [Development Skills](#development-skills)
2. [When to Use Each Skill](#when-to-use-each-skill)
3. [Core Project Standards](#core-project-standards)
4. [Best Practices Summary](#best-practices-summary)

---

## Development Skills

### 1. **FastAPI Templates** 🚀

**Description:** Create production-ready FastAPI projects with async patterns, dependency injection, and comprehensive error handling.

**When to Use:**

- Starting new API features or refactoring existing endpoints
- Implementing async route handlers
- Setting up database connections and sessions
- Creating complex business logic with proper layering
- Structuring services, repositories, and controllers

**Key Concepts:**

- Project structure: api → services → repositories
- Async/await patterns for all I/O operations
- Dependency injection with FastAPI's `Depends`
- Proper exception handling and response formatting

---

### 2. **API Security Best Practices** 🔐

**Description:** Implement secure API design patterns including authentication, authorization, input validation, rate limiting, and protection against common API vulnerabilities.

**When to Use:**

- Designing new API endpoints
- Implementing authentication and authorization
- Protecting against injection attacks and XSS
- Setting up rate limiting and throttling
- Handling sensitive user data
- Performing security audits

**Key Topics Covered:**

- JWT and OAuth 2.0 authentication
- Role-based access control (RBAC)
- Input validation and sanitization
- Rate limiting and throttling
- OWASP API Top 10 protection
- Secure error messages and headers

---

### 3. **Security Review** 🛡️

**Description:** Comprehensive security checklist for authentication, input validation, SQL injection prevention, authorization, XSS prevention, and sensitive data handling.

**When to Use:**

- Implementing authentication or authorization features
- Handling user input or file uploads
- Creating new API endpoints with sensitive operations
- Working with secrets or credentials
- Implementing payment features
- Storing or transmitting sensitive data

**Security Checklist Includes:**

- Secrets management (no hardcoded API keys)
- Input validation with schemas
- SQL injection prevention (parameterized queries)
- Authentication & authorization checks
- Row Level Security (RLS) implementation
- XSS prevention with sanitization

---

### 4. **Python Design Patterns** 🏗️

**Description:** Python design patterns including KISS, Separation of Concerns, Single Responsibility, and composition over inheritance.

**When to Use:**

- Designing new components or services
- Refactoring complex or tangled code
- Deciding whether to create an abstraction
- Choosing between inheritance and composition
- Evaluating code complexity and coupling
- Planning modular architectures

**Core Principles:**

- **KISS:** Keep it Simple, Stupid (simplest solution that works)
- **SRP:** Single Responsibility Principle (one reason to change)
- **Separation of Concerns:** API Layer → Service Layer → Repository Layer
- **Composition Over Inheritance:** Build behavior by combining objects

---

### 5. **Python Type Safety** 📝

**Description:** Python type safety with type hints, generics, protocols, and strict type checking using mypy/pyright.

**When to Use:**

- Adding type hints to existing code
- Creating generic, reusable classes
- Defining structural interfaces with protocols
- Configuring mypy or pyright for strict checking
- Building type-safe APIs and libraries

**Best Practices:**

- Annotate all public function signatures
- Use modern Union syntax (`str | None` instead of `Optional[str]`)
- Type narrowing with guards
- Generic classes for reusable patterns
- Enable strict typing in CI/CD pipeline

---

### 6. **Logging Best Practices** 📊

**Description:** Logging best practices focused on wide events (canonical log lines) for powerful debugging and analytics.

**When to Use:**

- Implementing logging in new features
- Adding observability to services
- Designing logging strategy for requests
- Debugging production issues
- Analytics and monitoring

**Core Principles:**

- **Wide Events:** Emit one context-rich event per request per service
- **High Cardinality:** Include user IDs, request IDs, transaction IDs
- **Business Context:** Log user subscription tier, cart value, feature flags
- **Environment Characteristics:** Include commit hash, service version, region
- **Single Logger:** Use one logger instance configured at startup
- **Middleware Pattern:** Handle wide event infrastructure in middleware

---

### 7. **Python Background Jobs** ⚙️

**Description:** Python background job patterns including task queues, workers, and event-driven architecture.

**When to Use:**

- Processing tasks longer than a few seconds
- Sending emails, notifications, or webhooks
- Generating reports or exporting data
- Processing uploads or media transformations
- Integrating with unreliable external services
- Building event-driven architectures

**Key Concepts:**

- Task Queue Pattern: Enqueue → Return ID → Process asynchronously
- Idempotency: Design for safe re-execution on retries
- Job State Machine: pending → running → succeeded/failed
- At-Least-Once Delivery: Handle duplicates gracefully

---

### 8. **Python Performance Optimization** ⚡

**Description:** Profile and optimize Python code using cProfile, memory profilers, and performance best practices.

**When to Use:**

- Identifying performance bottlenecks
- Reducing application latency
- Optimizing CPU-intensive operations
- Reducing memory consumption
- Improving database query performance
- Speeding up data processing pipelines

**Tools and Techniques:**

- **cProfile:** CPU profiling for time-consuming functions
- **line_profiler:** Line-by-line profiling granularity
- **memory_profiler:** Track memory allocation and leaks
- **Algorithmic optimization:** Better algorithms and data structures
- **Parallelization:** Multi-threading/processing where applicable
- **Caching:** Avoid redundant computation

---

### 9. **SQL Optimization Patterns** 🗄️

**Description:** SQL query optimization, indexing strategies, and EXPLAIN analysis for better database performance.

**When to Use:**

- Debugging slow-running queries
- Designing performant database schemas
- Optimizing application response times
- Improving scalability
- Analyzing EXPLAIN query plans
- Implementing efficient indexes
- Resolving N+1 query problems

**Key Optimization Areas:**

- EXPLAIN ANALYZE for query plans
- Index strategies (B-Tree, Hash, GIN, BRIN)
- Eliminate N+1 queries with JOINs
- Optimize pagination for large tables
- Column selection (avoid SELECT \*)
- JOIN optimization

---

### 10. **KISS, DRY, YAGNI** 🎯

**Description:** Code quality principles for simplicity, reducing duplication, and avoiding unnecessary features.

**When to Use:**

- Reviewing code quality
- Refactoring complex code
- Making architectural decisions
- Evaluating when abstractions are needed

**Quick Reference:**

- **KISS:** Methods < 20 lines, complexity < 10, indent < 3 levels
- **DRY:** Abstract after 3 occurrences, single source of truth
- **YAGNI:** Only build what's explicitly required NOW
- **Early returns:** Prefer guard clauses over nested else
- **Composition:** Prefer over inheritance

---

### 11. **Code Review Excellence** 👀

**Description:** Master effective code review practices to provide constructive feedback, catch bugs early, and foster knowledge sharing.

**When to Use:**

- Reviewing pull requests
- Establishing code review standards
- Mentoring junior developers
- Conducting architecture reviews
- Improving team collaboration

**Review Process:**

1. **Phase 1:** Context gathering (2-3 minutes)
2. **Phase 2:** High-level review (5-10 minutes)
3. **Phase 3:** Line-by-line review (10-20 minutes)
4. **Phase 4:** Summary & decision (2-3 minutes)

**Review Focus Areas:**

- Logic correctness and edge cases
- Security vulnerabilities
- Performance implications
- Test coverage and quality
- Error handling
- Documentation and comments
- API design and naming

---

### 12. **Code Review Expert** 🔍

**Description:** Expert code review with SOLID analysis, architecture evaluation, security scanning, and removal candidates.

**When to Use:**

- Performing in-depth code reviews
- Detecting SOLID violations
- Identifying security risks
- Finding unused or redundant code
- Planning refactoring work
- Pre-production code quality checks

**Review Severity Levels:**

- **P0 - Critical:** Security vulnerability, data loss risk, correctness bug
- **P1 - High:** Logic error, significant SOLID violation, performance regression
- **P2 - Medium:** Code smell, maintainability concern, minor SOLID violation
- **P3 - Low:** Style, naming, minor suggestion

---

### 13. **Memory Safety Patterns** 🧠

**Description:** Memory-safe programming patterns (less applicable for pure Python, but useful for understanding concepts).

**When to Use:**

- Writing Python extensions in C/Rust
- Understanding memory management principles
- Building systems code
- Preventing memory leaks

**Core Patterns:**

- RAII (Resource Acquisition Is Initialization)
- Ownership and borrowing concepts
- Smart pointers and resource management

---

### 14. **Docs Writer** 📚

**Description:** Technical writing and documentation standards for clarity, consistency, and accuracy.

**When to Use:**

- Writing or editing documentation
- Creating README files
- Writing API documentation
- Updating project guides
- Improving documentation clarity

**Documentation Standards:**

- Professional, friendly, and direct tone
- Address reader as "you", use active voice
- Simple vocabulary, avoid jargon
- Clear requirements ("must") vs recommendations ("we recommend")
- Semantic HTML and accessibility
- Consistent formatting and structure

---

## When to Use Each Skill

### By Task Type

#### Starting a new feature

1. **Python Design Patterns** - Plan architecture
2. **FastAPI Templates** - Set up project structure
3. **API Security Best Practices** - Secure endpoints
4. **Python Type Safety** - Add type hints

#### Writing business logic

1. **Python Design Patterns** - Design components
2. **Python Type Safety** - Use type hints
3. **KISS, DRY, YAGNI** - Keep code simple and maintainable
4. **Logging Best Practices** - Add observability

#### Working with databases

1. **SQL Optimization Patterns** - Optimize queries
2. **FastAPI Templates** - Set up repositories
3. **Python Type Safety** - Type repository methods

#### Implementing background jobs

1. **Python Background Jobs** - Design task queue
2. **Logging Best Practices** - Monitor job execution
3. **Error Handling** - Implement retries

#### Security-sensitive features

1. **Security Review** - Complete security checklist
2. **API Security Best Practices** - Implement authentication
3. **SQL Optimization Patterns** - Prevent SQL injection

#### Code review

1. **Code Review Excellence** - Constructive feedback
2. **Code Review Expert** - Detect violations and risks
3. **Python Design Patterns** - Architecture assessment
4. **Security Review** - Security check

#### Performance issues

1. **Python Performance Optimization** - Profile and optimize
2. **SQL Optimization Patterns** - Optimize queries
3. **Python Background Jobs** - Defer heavy work

---

## Core Project Standards

### FastAPI Project Structure

```
app/
├── api/                    # API routes and endpoints
│   ├── __init__.py
│   └── jobs.py            # Background job definitions
├── configs/               # Configuration and setup
│   ├── database_configuration.py
│   ├── environment_configuration.py
│   ├── redis_configuration.py
│   └── worker_configuration.py
├── controllers/           # Request/response handling (if using)
│   └── __init__.py
├── dtos/                  # Data Transfer Objects
│   ├── api_response_dto.py
│   └── __init__.py
├── exceptions/            # Custom exceptions
│   ├── base.py
│   └── __init__.py
├── lib/                   # Shared utilities
│   ├── db.py             # Database utilities
│   ├── logging.py        # Logging configuration
│   ├── response_formatter.py
│   └── __init__.py
├── models/                # Database models
│   └── __init__.py
├── repositories/          # Data access layer
│   └── __init__.py
├── services/              # Business logic layer
│   └── __init__.py
├── workers/               # Background job workers
│   ├── hello_world.py
│   └── __init__.py
└── main.py              # Application entry point
```

### Architecture Layers

```
┌─────────────────────────────────────────────────┐
│  API Layer (api/)                               │
│  - Parse requests                               │
│  - Validate input                               │
│  - Return responses                             │
└─────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────┐
│  Service Layer (services/)                      │
│  - Business logic                               │
│  - Domain rules                                 │
│  - Orchestration                                │
└─────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────┐
│  Repository Layer (repositories/)               │
│  - Database queries                             │
│  - Data persistence                             │
│  - Data access abstraction                      │
└─────────────────────────────────────────────────┘
```

### Type Safety Standards

- All public functions must have type hints
- Use `str | None` instead of `Optional[str]`
- Enable `mypy --strict` in CI/CD
- Type all repository and service methods
- Use generics for reusable patterns

### Security Standards

- Never hardcode secrets (use environment variables)
- Validate all user input with schemas
- Use parameterized queries for database
- Implement proper authentication/authorization
- Use HTTPS and secure cookies
- Sanitize error messages (no data leaks)
- Log security events with context

### Logging Standards

- Emit one wide event per request per service
- Include request ID for tracing
- Include business context (user ID, subscription tier, etc.)
- Include environment characteristics (version, commit hash, region)
- Use structured JSON logging
- Log at request completion in finally block

### Database Standards

- Use parameterized queries (no string concatenation)
- Index frequently queried columns
- Use composite indexes for multi-column queries
- Avoid SELECT \* - specify needed columns
- Optimize JOINs and use EXPLAIN ANALYZE
- Implement N+1 query prevention

---

## Best Practices Summary

### Code Quality

- ✅ Keep functions < 20 lines
- ✅ Use KISS principle - simple is better
- ✅ Follow DRY - don't repeat yourself
- ✅ Apply YAGNI - don't build unnecessary features
- ✅ Prefer composition over inheritance
- ✅ Use single responsibility principle

### Testing

- ✅ Write tests for business logic
- ✅ Cover edge cases and error conditions
- ✅ Use descriptive test names
- ✅ Keep tests deterministic
- ✅ Mock external dependencies

### Error Handling

- ✅ Use custom exceptions for different error types
- ✅ Provide meaningful error messages
- ✅ Don't leak sensitive information in errors
- ✅ Log errors with full context
- ✅ Implement proper retry logic for background jobs

### Documentation

- ✅ Document public APIs with docstrings
- ✅ Add type hints for clarity
- ✅ Keep README.md updated
- ✅ Document configuration options
- ✅ Add examples for complex features

### Performance

- ✅ Profile before optimizing
- ✅ Use EXPLAIN ANALYZE for queries
- ✅ Implement caching for expensive operations
- ✅ Use background jobs for long-running tasks
- ✅ Monitor and log performance metrics

### Security

- ✅ Never commit secrets to git
- ✅ Validate all user inputs
- ✅ Use parameterized queries
- ✅ Implement RBAC for API endpoints
- ✅ Use HTTPS/TLS for all communications
- ✅ Use httpOnly, Secure, SameSite cookies

---

## How to Get Help

For any development task:

1. **Identify the task type** (e.g., "adding a new API endpoint")
2. **Find the relevant skills** from the table above
3. **Read the specific skill section** for that task
4. **Follow the patterns and best practices** outlined
5. **Refer back to this document** when in doubt

Remember: This backend follows clean architecture principles with clear separation between API, Service, and Repository layers. Always prioritize code clarity, maintainability, and security.

---

**Last Updated:** February 2026
**Project:** Simulation App Backend
**Tech Stack:** FastAPI, Python 3.10+, PostgreSQL, Redis
