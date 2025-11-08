# Docker Stack Naming Convention

## Overview

All Docker resources (containers, volumes, networks) follow a consistent naming pattern:
```
linkedin-gateway-{edition}-{resource-type}
```

---

## Core Edition

### Project Name
```
linkedin-gateway-core
```

### Containers
- `linkedin-gateway-core-db` - PostgreSQL 17 database
- `linkedin-gateway-core-api` - FastAPI backend

### Volumes
- `linkedin-gateway-core-postgres-data` - Database persistent storage
- `linkedin-gateway-core-backend-logs` - Application logs

### Network
- `linkedin-gateway-core-network` - Internal bridge network

---

## SaaS Edition

### Project Name
```
linkedin-gateway-saas
```

### Containers
- `linkedin-gateway-saas-db` - PostgreSQL 17 database
- `linkedin-gateway-saas-api` - FastAPI backend

### Volumes
- `linkedin-gateway-saas-postgres-data` - Database persistent storage
- `linkedin-gateway-saas-backend-logs` - Application logs

### Network
- `linkedin-gateway-saas-network` - Internal bridge network

---

## Benefits

✅ **Clear Identification** - Easy to identify which edition a resource belongs to
✅ **Parallel Deployment** - Can run both editions simultaneously without conflicts
✅ **Easy Management** - Filter resources by edition using `docker ps | grep linkedin-gateway-core`
✅ **Consistent Naming** - All resources follow the same pattern

---

## Docker Commands

### List Resources by Edition

```bash
# Core edition
docker ps | findstr linkedin-gateway-core
docker volume ls | findstr linkedin-gateway-core
docker network ls | findstr linkedin-gateway-core

# SaaS edition
docker ps | findstr linkedin-gateway-saas
docker volume ls | findstr linkedin-gateway-saas
docker network ls | findstr linkedin-gateway-saas
```

### Stop Specific Edition

```bash
# Core
docker compose -f deployment/docker-compose.yml down

# SaaS
docker compose -f deployment/docker-compose.yml -f deployment/docker-compose.saas.yml down
```

### Remove All Resources (including volumes)

```bash
# Core
docker compose -f deployment/docker-compose.yml down -v

# SaaS
docker compose -f deployment/docker-compose.yml -f deployment/docker-compose.saas.yml down -v
```

---

## Implementation

The naming is defined in `docker-compose.yml` and `docker-compose.saas.yml`:

```yaml
# docker-compose.yml
name: linkedin-gateway-core

services:
  postgres:
    container_name: linkedin-gateway-core-db
  backend:
    container_name: linkedin-gateway-core-api

volumes:
  postgres_data:
    name: linkedin-gateway-core-postgres-data
  backend_logs:
    name: linkedin-gateway-core-backend-logs

networks:
  linkedin_gateway_network:
    name: linkedin-gateway-core-network
```

```yaml
# docker-compose.saas.yml
name: linkedin-gateway-saas

services:
  postgres:
    container_name: linkedin-gateway-saas-db
  backend:
    container_name: linkedin-gateway-saas-api

volumes:
  postgres_data:
    name: linkedin-gateway-saas-postgres-data
  backend_logs:
    name: linkedin-gateway-saas-backend-logs

networks:
  linkedin_gateway_network:
    name: linkedin-gateway-saas-network
```

---

## Future Editions

When adding new editions (e.g., Enterprise), follow the same pattern:

```
linkedin-gateway-enterprise-db
linkedin-gateway-enterprise-api
linkedin-gateway-enterprise-postgres-data
linkedin-gateway-enterprise-backend-logs
linkedin-gateway-enterprise-network
```

