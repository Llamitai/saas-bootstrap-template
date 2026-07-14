import { InvitationPageView } from "@/features/auth";

export default async function InvitationPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  return <InvitationPageView params={params} />;
}
