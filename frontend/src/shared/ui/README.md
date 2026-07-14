# Shared UI

`shared/ui` owns design-system primitives: buttons, inputs, overlays, layout primitives, table primitives, navigation primitives, loading primitives, and low-level date controls.

Rules:

- Components here must not know about a product feature, tenant, or backend endpoint.
- Components here may import `shared/lib`, `shared/config/public`, and other `shared/ui` modules.
- Feature-specific viewers and editors stay outside this folder until their owning feature slice is migrated.

Moved in phase 2.4:

- `action-button`, `alert`, `alert-dialog`, `avatar`, `badge`, `breadcrumb`, `button`, `calendar`, `card`, `checkbox`, `collapsible`, `combobox`, `date-range-picker`, `dialog`, `dropdown-menu`, `field`, `input`, `input-group`, `label`, `popover`, `scroll-area`, `select`, `separator`, `sheet`, `sidebar`, `skeleton`, `spinner`, `switch`, `table`, `tabs`, `textarea`, `toggle`, `toggle-group`, `tooltip`.

Moved in phase 2.5:

- `base-list-row`, `confirm-delete-dialog`, `date-time-label`, `date-range-filter`, `editable-inline-name`, `empty-state`, `inline-meta`, `multi-select-filter`, `page-content`, `search-input-filter`, `short-id`, `show`, `status-ring`, `tabs-with-actions`.

Deferred:

- Feature-specific viewers and editors need ownership review before moving.
