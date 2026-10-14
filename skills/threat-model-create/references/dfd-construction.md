# Data Flow Diagram Construction

DFDs are the foundation of STRIDE threat modeling. They show how data moves through a system and where trust levels change.

## DFD Elements

### Notation

| Element | Symbol | Description |
|---|---|---|
| External Entity | Rectangle | Actor outside the system boundary |
| Process | Circle/Rounded rect | Code that transforms data |
| Data Store | Parallel lines | Persistent storage |
| Data Flow | Arrow | Data movement between elements |
| Trust Boundary | Dashed line | Where trust level changes |

### Naming Conventions

- **External Entities:** Role-based names — "Authenticated User", "Admin", "Payment Gateway"
- **Processes:** Verb-noun — "Validate Input", "Process Payment", "Generate Report"
- **Data Stores:** What they hold — "User Database", "Session Cache", "Audit Log"
- **Data Flows:** What they carry — "Login Credentials", "JWT Token", "Query Results"

## Building the DFD

### Step 1: Identify Entry Points

Start from outside in. Every way data enters or leaves your system is an entry point:

- HTTP/HTTPS endpoints (REST, GraphQL, WebSocket)
- CLI commands
- File uploads/downloads
- Message queue consumers/producers
- Scheduled jobs (cron, timers)
- Admin interfaces

For existing systems, find entry points in the code:

```bash
# Find route/endpoint definitions
grep -r "route\|handler\|endpoint\|@app\.\|@Get\|@Post\|@api" --include="*.py" --include="*.rs" --include="*.go" --include="*.js" --include="*.ts" -l
```

### Step 2: Map Data Stores

Identify every place data persists:

- Primary database (PostgreSQL, MySQL, SQLite)
- Cache (Redis, Memcached)
- File system (uploads, configs, logs)
- External storage (S3, GCS)
- Message queues (RabbitMQ, Kafka)
- Secrets (Vault, environment variables, config files)

### Step 3: Draw Data Flows

For each entry point, trace the data path:

1. Where does input data come from?
2. What process handles it first?
3. What validation or transformation happens?
4. Where does the data get stored (if anywhere)?
5. Where does the data go next?
6. What response flows back?

### Step 4: Mark Trust Boundaries

A trust boundary exists wherever:

- Network boundary changes (internet → internal, DMZ → backend)
- Authentication state changes (anonymous → authenticated)
- Authorization level changes (user → admin)
- Code ownership changes (your code → third-party library)
- Process isolation changes (container → host, sandbox → kernel)
- Data sensitivity changes (public → internal → confidential)

Every data flow that crosses a trust boundary is a potential attack vector. These crossings are where you'll focus your STRIDE analysis.

## Markdown DFD Representation

When you can't use graphical tools, represent DFDs in structured markdown:

```markdown
## System: E-Commerce Platform

### External Entities
- **EU-1:** Web Browser (unauthenticated user)
- **EU-2:** Web Browser (authenticated customer)
- **EU-3:** Admin Dashboard
- **EU-4:** Payment Gateway (Stripe)

### Processes
- **P-1:** API Gateway (authentication, routing, rate limiting)
- **P-2:** Order Service (order creation, fulfillment tracking)
- **P-3:** Payment Service (charge processing, refunds)
- **P-4:** Notification Service (email, push notifications)

### Data Stores
- **DS-1:** PostgreSQL (users, orders, products)
- **DS-2:** Redis (sessions, rate limit counters)
- **DS-3:** S3 (product images, invoices)
- **DS-4:** Audit Log (append-only event store)

### Trust Boundaries
- **TB-1:** Internet ↔ API Gateway (all external traffic)
- **TB-2:** API Gateway ↔ Internal Services (authenticated requests)
- **TB-3:** Services ↔ Database (application → data layer)
- **TB-4:** Services ↔ Payment Gateway (internal → external)

### Data Flows
| ID | From | To | Data | Crosses Boundary |
|---|---|---|---|---|
| DF-1 | EU-1 | P-1 | Login credentials | TB-1 |
| DF-2 | P-1 | DS-2 | Session token | TB-3 |
| DF-3 | EU-2 | P-1 | Order request | TB-1 |
| DF-4 | P-1 | P-2 | Validated order | TB-2 |
| DF-5 | P-2 | DS-1 | Order record | TB-3 |
| DF-6 | P-2 | P-3 | Payment request | TB-2 |
| DF-7 | P-3 | EU-4 | Charge request | TB-4 |
| DF-8 | EU-4 | P-3 | Payment result | TB-4 |
| DF-9 | P-2 | P-4 | Notification request | TB-2 |
| DF-10 | P-2 | DS-4 | Audit event | TB-3 |
```

## Common Patterns

### Web Application DFD

```
[Browser] --HTTPS--> [Load Balancer] --HTTP--> [App Server] --SQL--> [Database]
                                                    |
                                                    +--HTTP--> [Cache]
                                                    |
                                                    +--HTTP--> [External API]

Trust Boundaries:
  TB-1: Internet ↔ Load Balancer
  TB-2: App Server ↔ Database
  TB-3: App Server ↔ External API
```

### Microservices DFD

```
[Client] --HTTPS--> [API Gateway] --gRPC--> [Service A] --SQL--> [DB-A]
                         |                       |
                         +--gRPC--> [Service B]  +--AMQP--> [Queue]
                                        |                      |
                                        +--SQL--> [DB-B]  [Service C]

Trust Boundaries:
  TB-1: Client ↔ API Gateway
  TB-2: API Gateway ↔ Each Service
  TB-3: Each Service ↔ Its Database
  TB-4: Services ↔ Message Queue
```

## Deriving DFDs from Existing Code

For projects without architecture documentation:

1. **Start with `docker-compose.yml` or deployment config** — this shows services and their connections
2. **Read the main entry point** — it reveals initialization order and dependencies
3. **Check environment variables** — they show external service connections
4. **Map imports/dependencies** — which services call which
5. **Check network configuration** — ports, protocols, TLS settings
6. **Review CI/CD pipelines** — they often reveal deployment boundaries and secret injection points

The DFD doesn't need to be perfect. Start rough, refine as you discover more during the STRIDE analysis.
