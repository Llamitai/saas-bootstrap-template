import type { LucideIcon } from "lucide-react";
import * as React from "react";

import { cn } from "@/shared/lib/utils";
import { EmptyState } from "@/shared/ui/empty-state";
import { Spinner } from "@/shared/ui/spinner";

interface TableProps extends React.HTMLAttributes<HTMLTableElement> {
  containerClassName?: string;
}

const Table = React.forwardRef<HTMLTableElement, TableProps>(
  ({ className, containerClassName, ...props }, ref) => (
    <div
      className={cn(
        "relative w-full overflow-auto rounded-lg bg-card ring-1 ring-border/70",
        containerClassName
      )}
    >
      <table
        ref={ref}
        className={cn("w-full caption-bottom text-sm", className)}
        {...props}
      />
    </div>
  )
);
Table.displayName = "Table";

interface TableSurfaceProps extends React.HTMLAttributes<HTMLDivElement> {
  toolbar?: React.ReactNode;
  viewportRef?: React.Ref<HTMLDivElement>;
  viewportClassName?: string;
}

const TableSurface = React.forwardRef<HTMLDivElement, TableSurfaceProps>(
  (
    { className, toolbar, viewportRef, viewportClassName, children, ...props },
    ref
  ) => (
    <div
      ref={ref}
      className={cn(
        "flex min-h-0 flex-1 flex-col rounded-lg border border-border/70 bg-card",
        className
      )}
      {...props}
    >
      {toolbar ? (
        <div className="relative z-20 shrink-0 border-b border-border/70 px-3 py-3">
          {toolbar}
        </div>
      ) : null}
      <div
        ref={viewportRef}
        className={cn(
          "flex min-h-0 flex-1 flex-col overflow-y-auto",
          toolbar ? "rounded-b-lg" : "rounded-lg",
          viewportClassName
        )}
      >
        {children}
      </div>
    </div>
  )
);
TableSurface.displayName = "TableSurface";

const TableSurfaceTable = React.forwardRef<HTMLTableElement, TableProps>(
  ({ containerClassName, ...props }, ref) => (
    <Table
      ref={ref}
      containerClassName={cn(
        "overflow-visible rounded-none bg-transparent ring-0",
        containerClassName
      )}
      {...props}
    />
  )
);
TableSurfaceTable.displayName = "TableSurfaceTable";

function TableSurfaceLoading({
  className,
  children,
}: {
  className?: string;
  children?: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        "flex min-h-[280px] flex-1 items-center justify-center py-12",
        className
      )}
    >
      {children ?? <Spinner className="h-5 w-5 text-muted-foreground" />}
    </div>
  );
}

interface TableSurfaceEmptyProps {
  icon: LucideIcon;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
  secondaryActionLabel?: string;
  onSecondaryAction?: () => void;
  secondaryActionIcon?: LucideIcon;
  className?: string;
}

function TableSurfaceEmpty({ className, ...props }: TableSurfaceEmptyProps) {
  return (
    <div
      className={cn(
        "flex min-h-[320px] flex-1 items-center justify-center py-12",
        className
      )}
    >
      <EmptyState variant="plain" {...props} />
    </div>
  );
}

const TableHeader = React.forwardRef<
  HTMLTableSectionElement,
  React.HTMLAttributes<HTMLTableSectionElement>
>(({ className, ...props }, ref) => (
  <thead
    ref={ref}
    className={cn("bg-muted/60 [&_tr]:border-b", className)}
    {...props}
  />
));
TableHeader.displayName = "TableHeader";

const TableBody = React.forwardRef<
  HTMLTableSectionElement,
  React.HTMLAttributes<HTMLTableSectionElement>
>(({ className, ...props }, ref) => (
  <tbody
    ref={ref}
    className={cn("[&_tr:last-child]:border-0", className)}
    {...props}
  />
));
TableBody.displayName = "TableBody";

const TableFooter = React.forwardRef<
  HTMLTableSectionElement,
  React.HTMLAttributes<HTMLTableSectionElement>
>(({ className, ...props }, ref) => (
  <tfoot
    ref={ref}
    className={cn(
      "border-t bg-muted/50 font-medium [&>tr]:last:border-b-0",
      className
    )}
    {...props}
  />
));
TableFooter.displayName = "TableFooter";

const TableRow = React.forwardRef<
  HTMLTableRowElement,
  React.HTMLAttributes<HTMLTableRowElement>
>(({ className, ...props }, ref) => (
  <tr
    ref={ref}
    className={cn(
      "border-b border-border/70 transition-colors hover:bg-muted/50 data-[state=selected]:bg-accent",
      className
    )}
    {...props}
  />
));
TableRow.displayName = "TableRow";

const TableHead = React.forwardRef<
  HTMLTableCellElement,
  React.ThHTMLAttributes<HTMLTableCellElement>
>(({ className, ...props }, ref) => (
  <th
    ref={ref}
    className={cn(
      "h-12 px-4 text-left align-middle text-xs font-semibold text-muted-foreground [&:has([role=checkbox])]:pr-0",
      className
    )}
    {...props}
  />
));
TableHead.displayName = "TableHead";

const TableCell = React.forwardRef<
  HTMLTableCellElement,
  React.TdHTMLAttributes<HTMLTableCellElement>
>(({ className, ...props }, ref) => (
  <td
    ref={ref}
    className={cn("p-4 align-middle [&:has([role=checkbox])]:pr-0", className)}
    {...props}
  />
));
TableCell.displayName = "TableCell";

const TableCaption = React.forwardRef<
  HTMLTableCaptionElement,
  React.HTMLAttributes<HTMLTableCaptionElement>
>(({ className, ...props }, ref) => (
  <caption
    ref={ref}
    className={cn("mt-4 text-sm text-muted-foreground", className)}
    {...props}
  />
));
TableCaption.displayName = "TableCaption";

export {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
  TableSurface,
  TableSurfaceEmpty,
  TableSurfaceLoading,
  TableSurfaceTable,
};
