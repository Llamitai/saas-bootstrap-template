import { HomeLayout } from "fumadocs-ui/layouts/home";
import {
  ArrowRight,
  Braces,
  Compass,
  Lightbulb,
  type LucideIcon,
  Rocket,
  Users,
} from "lucide-react";
import { Link } from "react-router";
import { baseOptions } from "@/lib/layout.shared";
import { appName } from "@/lib/shared";

export function meta() {
  return [
    { title: `${appName} Docs` },
    {
      name: "description",
      content: `Documentación técnica de ${appName}: guías, conceptos y referencia de la API.`,
    },
  ];
}

interface Section {
  title: string;
  description: string;
  href: string;
  icon: LucideIcon;
}

const sections: Section[] = [
  {
    title: "Empezar",
    description:
      "Instala el entorno local, recorre el repositorio y crea un proyecto desde la plantilla.",
    href: "/docs",
    icon: Rocket,
  },
  {
    title: "Guías",
    description:
      "Pasos concretos para módulos backend, features frontend, migraciones y documentación.",
    href: "/docs/guias",
    icon: Compass,
  },
  {
    title: "Conceptos",
    description:
      "Arquitectura backend y frontend, dominio multi-tenant y modelo de datos.",
    href: "/docs/conceptos",
    icon: Lightbulb,
  },
  {
    title: "Referencia",
    description:
      "API REST generada desde OpenAPI, recetas de just y contratos de miembros.",
    href: "/docs/referencia",
    icon: Braces,
  },
  {
    title: "Equipo",
    description:
      "Perfil del proyecto, verificación, flujo de cambios y decisiones de arquitectura.",
    href: "/docs/equipo",
    icon: Users,
  },
];

const commands = [
  [
    "just backend dev",
    "API, PostgreSQL, Redis, RustFS (S3), Mailpit y Directus en :8200",
  ],
  ["just frontend dev", "App Next.js en :3000"],
  ["just docs dev", "Este sitio en :4321"],
];

export default function Home() {
  return (
    <HomeLayout {...baseOptions()}>
      <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-12 px-4 py-12 md:px-6 md:py-16">
        <section className="flex flex-col gap-5">
          <p className="w-fit rounded-full border bg-fd-card px-3 py-1 text-xs font-medium text-fd-muted-foreground">
            FastAPI · Next.js · multi-tenant
          </p>
          <h1 className="max-w-3xl text-3xl font-semibold tracking-tight md:text-4xl">
            Documentación técnica de {appName}
          </h1>
          <p className="max-w-2xl text-base leading-7 text-fd-muted-foreground">
            Base para productos B2B autenticados: auth, tenants, miembros,
            invitaciones, roles, perfil, assets y consola interna. Aquí está
            cómo funciona, cómo extenderla y cómo verificar cada cambio.
          </p>
          <div className="flex flex-wrap gap-3">
            <Link
              className="inline-flex items-center gap-2 rounded-lg bg-fd-primary px-4 py-2 text-sm font-medium text-fd-primary-foreground transition-opacity hover:opacity-90"
              to="/docs"
            >
              Empezar
              <ArrowRight aria-hidden="true" className="size-4" />
            </Link>
            <Link
              className="inline-flex items-center gap-2 rounded-lg border bg-fd-card px-4 py-2 text-sm font-medium transition-colors hover:bg-fd-accent"
              to="/docs/referencia"
            >
              Referencia de la API
            </Link>
          </div>
        </section>

        <section
          aria-labelledby="sections-title"
          className="flex flex-col gap-4"
        >
          <h2
            id="sections-title"
            className="text-sm font-medium text-fd-muted-foreground"
          >
            Secciones
          </h2>
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {sections.map(({ title, description, href, icon: Icon }) => (
              <li key={href}>
                <Link
                  className="group flex h-full flex-col gap-3 rounded-xl border bg-fd-card p-5 transition-colors hover:border-fd-primary/40 hover:bg-fd-accent/40"
                  to={href}
                >
                  <span className="flex size-9 items-center justify-center rounded-lg border bg-fd-background text-fd-primary">
                    <Icon aria-hidden="true" className="size-4" />
                  </span>
                  <span className="flex items-center gap-1 font-medium">
                    {title}
                    <ArrowRight
                      aria-hidden="true"
                      className="size-3.5 opacity-0 transition-opacity group-hover:opacity-100"
                    />
                  </span>
                  <span className="text-sm leading-6 text-fd-muted-foreground">
                    {description}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>

        <section
          aria-labelledby="commands-title"
          className="flex flex-col gap-4"
        >
          <h2
            id="commands-title"
            className="text-sm font-medium text-fd-muted-foreground"
          >
            Arranque local
          </h2>
          <dl className="divide-y overflow-hidden rounded-xl border bg-fd-card">
            {commands.map(([command, detail]) => (
              <div
                key={command}
                className="flex flex-col gap-1 px-5 py-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <dt>
                  <code className="font-mono text-sm">{command}</code>
                </dt>
                <dd className="text-sm text-fd-muted-foreground">{detail}</dd>
              </div>
            ))}
          </dl>
        </section>
      </main>
    </HomeLayout>
  );
}
