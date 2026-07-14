import { ResetPasswordConfirmView } from "@/features/auth";

export default async function ResetPasswordTokenPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  return <ResetPasswordConfirmView token={token} />;
}
