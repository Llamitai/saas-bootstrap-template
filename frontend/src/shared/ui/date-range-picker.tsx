"use client";

import { Popover as PopoverPrimitive } from "@base-ui/react/popover";
import { CalendarDays } from "lucide-react";
import { useState } from "react";
import { cn } from "@/shared/lib/utils";
import { Calendar, dateToIso } from "@/shared/ui/calendar";

interface DateRangePickerProps {
  fromDate: string;
  toDate: string;
  onFromChange: (date: string) => void;
  onToChange: (date: string) => void;
  placeholder?: string;
  className?: string;
}

function addMonths(
  year: number,
  month: number,
  delta: number
): { year: number; month: number } {
  const d = new Date(year, month + delta, 1);
  return { year: d.getFullYear(), month: d.getMonth() };
}

function fmtDate(iso: string): string {
  return dateFromIso(iso).toLocaleDateString("es-MX", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function dateFromIso(iso: string): Date {
  return new Date(`${iso}T00:00:00`);
}

function selectedDayCount(from: string, to: string): number {
  return (
    Math.round(
      (dateFromIso(to).getTime() - dateFromIso(from).getTime()) / 86400000
    ) + 1
  );
}

function formatDisplay(from: string, to: string): string {
  if (from && to) return `${fmtDate(from)} — ${fmtDate(to)}`;
  if (from) return `Desde: ${fmtDate(from)}`;
  return "Seleccionar fechas";
}

export function DateRangePicker({
  fromDate,
  toDate,
  onFromChange,
  onToChange,
  placeholder = "Seleccionar fechas",
  className,
}: DateRangePickerProps) {
  const now = new Date();
  const [leftYear, setLeftYear] = useState(now.getFullYear());
  const [leftMonth, setLeftMonth] = useState(now.getMonth());
  const [hoverDate, setHoverDate] = useState("");
  const [open, setOpen] = useState(false);

  const right = addMonths(leftYear, leftMonth, 1);

  function handlePrev() {
    const prev = addMonths(leftYear, leftMonth, -1);
    setLeftYear(prev.year);
    setLeftMonth(prev.month);
  }

  function handleNext() {
    const next = addMonths(leftYear, leftMonth, 1);
    setLeftYear(next.year);
    setLeftMonth(next.month);
  }

  function handleSelect(iso: string) {
    if (!fromDate || (fromDate && toDate)) {
      // Start new selection
      onFromChange(iso);
      onToChange("");
    } else {
      // Second click: set to or swap
      if (iso < fromDate) {
        onToChange(fromDate);
        onFromChange(iso);
      } else {
        onToChange(iso);
      }
    }
  }

  const hasValue = !!(fromDate || toDate);
  const displayText = hasValue ? formatDisplay(fromDate, toDate) : placeholder;

  return (
    <PopoverPrimitive.Root
      open={open}
      onOpenChange={(isOpen) => {
        setOpen(isOpen);
        if (!isOpen) setHoverDate("");
      }}
    >
      <PopoverPrimitive.Trigger
        className={cn(
          "inline-flex h-10 items-center gap-2 rounded-lg border border-transparent bg-muted px-4 text-sm font-medium shadow-none",
          "hover:bg-accent hover:text-accent-foreground transition-colors",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
          hasValue && "bg-accent text-accent-foreground",
          className
        )}
      >
        <CalendarDays className="h-4 w-4 text-muted-foreground" />
        <span
          className={hasValue ? "text-foreground" : "text-muted-foreground"}
        >
          {displayText}
        </span>
        {hasValue && (
          <button
            type="button"
            aria-label="Limpiar fechas"
            onClick={(e) => {
              e.stopPropagation();
              onFromChange("");
              onToChange("");
              setHoverDate("");
            }}
            className="ml-1 rounded-lg text-muted-foreground hover:text-foreground transition-colors"
          >
            ×
          </button>
        )}
      </PopoverPrimitive.Trigger>

      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Positioner
          side="bottom"
          align="end"
          sideOffset={8}
          className="z-50 outline-none"
        >
          <PopoverPrimitive.Popup
            onMouseDown={(e) => e.preventDefault()}
            className={cn(
              "rounded-lg bg-popover p-4 shadow-overlay ring-1 ring-border/70 outline-none",
              "data-starting-style:opacity-0 data-starting-style:scale-95",
              "data-ending-style:opacity-0 data-ending-style:scale-95",
              "transition-[opacity,transform] duration-150"
            )}
          >
            <div className="flex gap-6" onMouseLeave={() => setHoverDate("")}>
              <Calendar
                month={leftMonth}
                year={leftYear}
                fromDate={fromDate}
                toDate={toDate}
                hoverDate={hoverDate}
                onSelect={handleSelect}
                onHover={setHoverDate}
                onPrevMonth={handlePrev}
                onNextMonth={handleNext}
                maxDate={dateToIso(new Date())}
                showPrevNav
                showNextNav={false}
              />
              <div className="w-px bg-border" />
              <Calendar
                month={right.month}
                year={right.year}
                fromDate={fromDate}
                toDate={toDate}
                hoverDate={hoverDate}
                onSelect={handleSelect}
                onHover={setHoverDate}
                onPrevMonth={handlePrev}
                onNextMonth={handleNext}
                maxDate={dateToIso(new Date())}
                showPrevNav={false}
                showNextNav
              />
            </div>

            {hasValue && (
              <div className="mt-4 flex items-center justify-between border-t border-border/70 pt-3">
                <span className="text-xs text-muted-foreground">
                  {fromDate && toDate
                    ? `${selectedDayCount(fromDate, toDate)} días seleccionados`
                    : "Selecciona la fecha final"}
                </span>
                <button
                  type="button"
                  onClick={() => {
                    onFromChange("");
                    onToChange("");
                    setHoverDate("");
                  }}
                  className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                >
                  Limpiar
                </button>
              </div>
            )}
          </PopoverPrimitive.Popup>
        </PopoverPrimitive.Positioner>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  );
}

export { dateToIso };
