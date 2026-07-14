export interface PermissionDefinition {
  code: string;
  label: string;
}

export interface PermissionCategory {
  id: string;
  label: string;
  permissions: PermissionDefinition[];
}

export const PERMISSIONS_CATALOG: PermissionCategory[] = [
  {
    id: "tenant_roles",
    label: "Roles",
    permissions: [
      { code: "tenant_roles.view", label: "Ver roles" },
      { code: "tenant_roles.create", label: "Crear roles" },
      { code: "tenant_roles.update", label: "Actualizar roles" },
      { code: "tenant_roles.delete", label: "Eliminar roles" },
      { code: "tenant_roles.assign", label: "Asignar roles" },
    ],
  },
  {
    id: "tenant_users",
    label: "Usuarios",
    permissions: [
      { code: "tenant_users.view", label: "Ver usuarios" },
      { code: "tenant_users.create", label: "Crear usuarios" },
      { code: "tenant_users.update", label: "Actualizar usuarios" },
      { code: "tenant_users.delete", label: "Eliminar usuarios" },
    ],
  },
  {
    id: "tenant_settings",
    label: "Configuraciones",
    permissions: [
      { code: "tenant_settings.view", label: "Ver configuraciones" },
      {
        code: "tenant_settings.update",
        label: "Actualizar configuraciones",
      },
      { code: "tenant_settings.delete", label: "Eliminar organizacion" },
    ],
  },
];

export const ALL_PERMISSION_CODES = PERMISSIONS_CATALOG.flatMap((cat) =>
  cat.permissions.map((p) => p.code)
);
