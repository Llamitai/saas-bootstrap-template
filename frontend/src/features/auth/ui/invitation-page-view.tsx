import Link from "next/link";
import { getTranslations } from "next-intl/server";
import { type ReactNode, Suspense } from "react";

import { loadInvitation } from "@/features/auth/api/invitations-server";
import { AcceptInvitationForm } from "@/features/auth/ui/accept-invitation-form";
import { Card } from "@/shared/ui/card";

function CenteredCard({ children }: { children: ReactNode }) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4">
      <Card className="w-full max-w-md gap-6 p-8">{children}</Card>
    </main>
  );
}

function StateHeader({
  tag,
  title,
  body,
}: {
  tag: string;
  title: string;
  body: string;
}) {
  return (
    <header className="space-y-2 text-center">
      <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted-foreground">
        {tag}
      </p>
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      <p className="text-sm text-muted-foreground">{body}</p>
    </header>
  );
}

export async function InvitationPageView({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const t = await getTranslations("Invitations");
  const { token } = await params;
  const result = await loadInvitation(token);

  if (result.kind === "already_accepted") {
    return (
      <CenteredCard>
        <StateHeader
          tag={t("tag")}
          title={t("alreadyAcceptedTitle")}
          body={t("alreadyAcceptedBody")}
        />
        <Link
          href="/"
          className="inline-flex h-12 w-full items-center justify-center rounded-lg bg-primary px-5 text-[13px] font-semibold text-primary-foreground shadow-raised transition hover:bg-primary/90"
        >
          {t("goToLogin")}
        </Link>
      </CenteredCard>
    );
  }

  if (result.kind === "expired") {
    return (
      <CenteredCard>
        <StateHeader
          tag={t("tag")}
          title={t("expiredTitle")}
          body={t("expiredBody")}
        />
      </CenteredCard>
    );
  }

  if (result.kind === "not_found") {
    return (
      <CenteredCard>
        <StateHeader
          tag={t("tag")}
          title={t("notFoundTitle")}
          body={t("notFoundBody")}
        />
      </CenteredCard>
    );
  }

  const invitation = result.data;

  return (
    <CenteredCard>
      <header className="space-y-2 text-center">
        <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted-foreground">
          {t("tag")}
        </p>
        <h1 className="text-2xl font-semibold tracking-tight">
          {t("invitedTo")}{" "}
          <span className="text-primary">{invitation.tenantName}</span>
        </h1>
        <p className="text-sm text-muted-foreground">
          {invitation.email}
          {invitation.roleName ? (
            <>
              <span className="mx-1.5">.</span>
              <span className="font-mono text-[10px] uppercase tracking-[0.18em]">
                {invitation.roleName}
              </span>
            </>
          ) : null}
        </p>
      </header>

      <Suspense>
        <AcceptInvitationForm
          token={token}
          requiresPassword={invitation.requiresPassword}
        />
      </Suspense>
    </CenteredCard>
  );
}
