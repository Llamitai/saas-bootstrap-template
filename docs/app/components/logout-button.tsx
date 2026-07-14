import { LogOut } from "lucide-react";
import { useSession } from "@/lib/session";

export function LogoutButton() {
  const session = useSession();

  if (!session.isAuthenticated) {
    return null;
  }

  return (
    <button
      className="docs-control-button"
      onClick={() => void session.logout()}
      type="button"
    >
      <LogOut aria-hidden="true" size={15} />
      Salir
    </button>
  );
}
