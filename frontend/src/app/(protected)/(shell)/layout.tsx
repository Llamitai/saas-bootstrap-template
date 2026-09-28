import type { ReactNode } from "react";
import { AppShell } from "@/features/app-shell";

// Mounted once for every shell page so the sidebar, its shared nav pill
// animation and the help panel persist across navigations.
export default function ShellLayout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
