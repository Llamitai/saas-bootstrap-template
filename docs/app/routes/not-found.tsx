import { HomeLayout } from "fumadocs-ui/layouts/home";
import { Link } from "react-router";
import { baseOptions } from "@/lib/layout.shared";
import { appName } from "@/lib/shared";

export function meta() {
  return [{ title: `No encontrado | ${appName} Docs` }];
}

export default function NotFound() {
  return (
    <HomeLayout {...baseOptions()}>
      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col justify-center gap-4 px-4 py-16">
        <p className="text-sm font-medium text-fd-muted-foreground">404</p>
        <h1 className="text-3xl font-semibold tracking-tight">
          Página no encontrada
        </h1>
        <p className="text-fd-muted-foreground">
          La ruta no existe. Usa la búsqueda o vuelve al inicio de la
          documentación.
        </p>
        <Link className="text-sm font-medium text-fd-primary" to="/docs">
          Volver a la documentación
        </Link>
      </main>
    </HomeLayout>
  );
}
