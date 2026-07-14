"use client";

import {
  CheckCircle2,
  Copy,
  ExternalLink,
  Mail,
  PartyPopper,
} from "lucide-react";
import { useState } from "react";
import { useOnboardTenantWizardStore } from "@/features/superuser/model/onboard-tenant-wizard-store";
import { Button } from "@/shared/ui/button";

export function StepVerify({ inviteBaseUrl }: { inviteBaseUrl: string }) {
  const result = useOnboardTenantWizardStore((s) => s.result);
  const skipEmail = useOnboardTenantWizardStore((s) => s.skipEmail);
  const [copied, setCopied] = useState<string | null>(null);

  if (!result) return null;

  const copyLink = async (token: string) => {
    const link = `${inviteBaseUrl.replace(/\/+$/, "")}/invitations/${token}`;
    await navigator.clipboard.writeText(link);
    setCopied(token);
    setTimeout(() => setCopied(null), 1500);
  };

  return (
    <div className="space-y-5">
      <div className="flex items-start gap-3 rounded-lg bg-success/10 p-4 ring-1 ring-success/20">
        <div className="relative flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-success/20">
          <PartyPopper className="h-5 w-5 text-success-deep" aria-hidden />
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="text-base font-semibold text-success-deep">
            ¡Tenant registrado exitosamente!
          </h3>
          <p className="text-sm text-success-deep/80">
            <span className="font-medium">{result.tenantName}</span> ya está
            listo para operar. Revisa los detalles abajo.
          </p>
        </div>
      </div>

      <ul className="space-y-2">
        <Check label={`Tenant "${result.tenantName}" creado`} />
        <Check label="Roles Admin y Member sembrados" />
        <Check label="Superusuario agregado como soporte (oculto en /members)" />
        <Check
          label={
            skipEmail
              ? `${result.invitations.length} invitaciones generadas (sin correo)`
              : `${result.invitations.length} correos de invitación enviados`
          }
        />
      </ul>

      {result.invitations.length > 0 && (
        <div className="rounded-lg bg-muted/50 ring-1 ring-border/60">
          <div className="px-3 py-2 border-b border-border/60 flex items-center justify-between">
            <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              Invitaciones pendientes
            </span>
          </div>
          <ul className="divide-y divide-border/60">
            {result.invitations.map((inv) => (
              <li key={inv.token} className="px-3 py-2 flex items-center gap-2">
                <Mail className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                <span className="text-sm flex-1 truncate">{inv.email}</span>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="gap-1.5 text-[11px]"
                  onClick={() => copyLink(inv.token)}
                >
                  <Copy className="h-3 w-3" />
                  {copied === inv.token ? "Copiado" : "Copiar link"}
                </Button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <a
        href={`/members?tenant=${result.tenantSlug}`}
        target="_blank"
        rel="noreferrer"
        className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline"
      >
        Abrir tenant en una nueva pestaña
        <ExternalLink className="h-3.5 w-3.5" />
      </a>
    </div>
  );
}

function Check({ label }: { label: string }) {
  return (
    <li className="flex items-center gap-2 text-sm">
      <CheckCircle2 className="h-4 w-4 shrink-0 text-success-deep" />
      <span>{label}</span>
    </li>
  );
}
