import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/shared/lib/utils";
import { Card } from "@/shared/ui/card";
import { LocaleSwitcher } from "@/shared/ui/components/locale-switcher";

interface AuthContainerProps {
  icon?: LucideIcon;
  brandMark?: ReactNode;
  iconContainerClassName?: string;
  sideVisual?: ReactNode;
  title: string;
  description: string;
  children: ReactNode;
}

export function AuthContainer({
  brandMark,
  icon: Icon,
  iconContainerClassName,
  sideVisual,
  title,
  description,
  children,
}: AuthContainerProps) {
  const fallbackVisual = (
    <div className="relative mx-auto aspect-[4/3] max-w-lg">
      <Card className="absolute inset-x-10 top-10 h-40 p-0" />
      <Card className="absolute inset-x-16 top-20 h-40 p-0" />
      <Card className="absolute inset-x-6 bottom-10 h-44 p-6">
        <div className="mb-5 h-3 w-32 rounded-full bg-muted" />
        <div className="grid gap-3">
          <div className="h-3 rounded-full bg-muted" />
          <div className="h-3 w-5/6 rounded-full bg-muted" />
          <div className="h-3 w-2/3 rounded-full bg-muted" />
        </div>
        <div className="absolute right-6 bottom-6 flex h-12 w-12 items-center justify-center rounded-full bg-accent text-accent-foreground">
          {brandMark ??
            (Icon ? <Icon className="h-6 w-6 text-primary" /> : null)}
        </div>
      </Card>
    </div>
  );

  return (
    <div className="relative grid min-h-screen bg-background lg:grid-cols-[3fr_2fr]">
      <div className="absolute top-4 right-4 z-10">
        <LocaleSwitcher />
      </div>

      <div className="hidden items-center justify-center bg-muted/40 p-12 lg:flex">
        <div className={cn("w-full", sideVisual ? "max-w-2xl" : "max-w-xl")}>
          {sideVisual ?? fallbackVisual}
        </div>
      </div>

      <div className="flex items-center justify-center p-6 sm:p-8">
        <div className="w-full max-w-md space-y-8">
          <div className="space-y-4 text-center">
            <div
              className={cn(
                "mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-accent text-accent-foreground",
                iconContainerClassName
              )}
            >
              {brandMark ??
                (Icon ? <Icon className="h-6 w-6 text-primary" /> : null)}
            </div>
            <div className="space-y-2">
              <h1 className="text-2xl font-semibold tracking-normal">
                {title}
              </h1>
              <p className="text-sm text-muted-foreground">{description}</p>
            </div>
          </div>

          {children}
        </div>
      </div>
    </div>
  );
}
