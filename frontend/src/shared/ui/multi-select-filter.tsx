import { Check, ChevronDown, SlidersHorizontal } from "lucide-react";
import * as React from "react";
import { cn } from "@/shared/lib/utils";
import { Badge } from "@/shared/ui/badge";
import { buttonVariants } from "@/shared/ui/button";

export interface FilterOption<T extends string> {
  label: string;
  value: T;
}

export interface MultiSelectFilterProps<T extends string> {
  title: string;
  selected: T[];
  onChange: (values: T[]) => void;
  options: FilterOption<T>[];
  className?: string;
  disabled?: boolean;
}

export function MultiSelectFilter<T extends string>({
  title,
  selected,
  onChange,
  options,
  className,
  disabled = false,
}: MultiSelectFilterProps<T>) {
  const [open, setOpen] = React.useState(false);
  const containerRef = React.useRef<HTMLDivElement>(null);
  const selectedSet = new Set(selected);

  React.useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setOpen(false);
      }
    };

    if (open) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [open]);

  const handleSelect = (value: T) => {
    const newSet = new Set(selectedSet);
    if (newSet.has(value)) {
      newSet.delete(value);
    } else {
      newSet.add(value);
    }
    onChange(Array.from(newSet));
  };

  return (
    <div ref={containerRef} className={cn("relative", className)}>
      <button
        type="button"
        onClick={() => !disabled && setOpen(!open)}
        disabled={disabled}
        aria-haspopup="menu"
        aria-expanded={open}
        className={cn(
          buttonVariants({ variant: "outline", size: "sm" }),
          "gap-2",
          selected.length > 0 &&
            "border-primary bg-accent/60 text-accent-foreground hover:bg-accent/70",
          disabled && "pointer-events-none opacity-40"
        )}
      >
        <SlidersHorizontal className="h-4 w-4 shrink-0 text-muted-foreground" />
        <span className="leading-5">{title}</span>
        {selected.length > 0 && (
          <>
            <span className="h-4 w-px bg-border" />
            <Badge variant="default" className="h-6 px-2 font-normal">
              {selected.length}
            </Badge>
          </>
        )}
        <ChevronDown
          className={cn(
            "h-4 w-4 text-muted-foreground transition-transform",
            open && "rotate-180"
          )}
        />
      </button>

      {open && (
        <div className="absolute top-full left-0 z-50 mt-2 w-56 rounded-lg bg-popover p-1.5 text-popover-foreground shadow-overlay ring-1 ring-border/70">
          <div className="px-2 py-1.5 text-sm font-semibold">{title}</div>
          <div className="border-t border-border/70" />
          <div className="py-1">
            {options.map((option, idx) => {
              const isSelected = selectedSet.has(option.value);
              return (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handleSelect(option.value)}
                  className="flex w-full cursor-pointer items-center gap-2 rounded-lg px-2.5 py-2 text-sm hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <div
                    className={cn(
                      "flex h-5 w-5 items-center justify-center rounded-sm border border-[var(--md3-field-indicator)]",
                      isSelected
                        ? "bg-primary text-primary-foreground"
                        : "opacity-50"
                    )}
                  >
                    {isSelected && <Check className="h-3 w-3" />}
                  </div>
                  {option.label}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
