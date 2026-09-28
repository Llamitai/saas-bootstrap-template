---
title: "Modelo de datos"
description: "Diagrama entidad-relación de las tablas del core."
icon: Table
---

Fuente de verdad: `backend/src/common/database/models/**` y las migraciones de
`backend/src/common/database/versions/`. Todas las tablas heredan `uuid`,
`created_at` y `updated_at` de `UUIDTimestampMixin`; el diagrama omite los
timestamps.

```mermaid
erDiagram
  users ||--o| email_addresses : email
  users ||--o| phone_numbers : phone
  users }o--o| tenants : current_tenant
  users ||--o{ tenants : owns
  tenants ||--o{ tenant_roles : roles
  tenants ||--o{ tenant_users : members
  tenants ||--o{ tenant_user_invitations : invitations
  tenant_roles ||--o{ tenant_users : assigned
  tenant_roles ||--o{ tenant_user_invitations : invited_as
  users ||--o{ tenant_users : membership
  users ||--o{ tenant_user_invitations : created_by

  users {
    uuid uuid PK
    string username
    string password
    string first_name
    string last_name
    uuid email_address_id FK
    uuid phone_number_id FK
    uuid current_tenant_id FK
    bool is_active
    bool is_superuser
    timestamp last_login
  }

  email_addresses {
    uuid uuid PK
    string email
    bool is_verified
  }

  phone_numbers {
    uuid uuid PK
    string iso_code
    string dial_code
    string phone_number
    string prefix
    bool is_verified
  }

  tenants {
    uuid uuid PK
    uuid owner_id FK
    string name
    string slug
    string status
    string time_zone
    string country_code
    string currency_code
    string logo_url
    bool is_deleted
  }

  tenant_roles {
    uuid uuid PK
    uuid tenant_id FK
    string name
    string slug
    string status
    string icon_url
    jsonb permissions
  }

  tenant_users {
    uuid uuid PK
    uuid tenant_id FK
    uuid user_id FK
    uuid tenant_role_id FK
    string first_name
    string last_name
    string photo
    bool is_owner
    bool is_support
    string status
    jsonb permissions
  }

  tenant_user_invitations {
    uuid uuid PK
    uuid tenant_id FK
    string email
    uuid tenant_role_id FK
    string token
    string status
    timestamp expires_at
    timestamp accepted_at
    uuid created_by_id FK
    bool requires_password
  }

  admin_api_keys {
    uuid uuid PK
    string name
    string key_prefix
    string key_hash
    json permissions
    bool is_revoked
    json tenants
  }
```

`admin_api_keys` no tiene claves foráneas: `tenants` guarda la lista de tenants a
los que la clave accede (`null` significa todos).
