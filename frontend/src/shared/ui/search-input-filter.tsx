import { Search } from "lucide-react";
import { cn } from "@/shared/lib/utils";
import { Input } from "@/shared/ui/input";

export interface SearchInputFilterProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
}

export function SearchInputFilter({
  value,
  onChange,
  placeholder = "Buscar...",
  className,
}: SearchInputFilterProps) {
  return (
    <div className={cn("relative w-[200px] lg:w-[250px]", className)}>
      <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
      <Input
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-10 w-full pl-8 text-xs sm:text-sm"
      />
    </div>
  );
}
