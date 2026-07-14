export {
  useCreateRoleMutation,
  useDeleteRoleMutation,
  useRolesQuery,
  useUpdateRoleMutation,
} from "@/features/roles/api/roles";
export type {
  CreateTenantRolePayload,
  DeleteResponse,
  TenantRole,
  UpdateTenantRolePayload,
} from "@/features/roles/model/types";
export { RolesView } from "@/features/roles/ui/roles-view";
