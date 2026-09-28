import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { ProfileView } from "@/features/profile";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("PageTitles");
  return { title: t("profile") };
}

export default function ProfilePage() {
  return <ProfileView />;
}
