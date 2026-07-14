export {
  useDeleteTenantMutation,
  useSettingsQuery,
  useUpdateAvatarMutation,
  useUpdateSettingsMutation,
} from "@/features/settings/api/settings";
export { useSettingsStore } from "@/features/settings/model/settings-store";
export type { TenantSettings } from "@/features/settings/model/types";
export {
  type SettingsTab,
  SettingsView,
} from "@/features/settings/ui/settings-view";
