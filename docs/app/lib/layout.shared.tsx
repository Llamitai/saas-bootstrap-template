import type { BaseLayoutProps } from "fumadocs-ui/layouts/shared";
import { BookOpenText } from "lucide-react";
import { appName } from "./shared";

export function baseOptions(): BaseLayoutProps {
  return {
    nav: {
      title: (
        <>
          <BookOpenText aria-hidden="true" className="size-5 text-fd-primary" />
          <span className="whitespace-nowrap font-semibold">{appName}</span>
          <span className="hidden text-fd-muted-foreground sm:inline">
            Docs
          </span>
        </>
      ),
      url: "/",
    },
  };
}
