import { forwardRef, type InputHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, invalid = false, ...props }, ref) => (
    <input
      className={cn(
        "h-11 w-full min-w-0 rounded-xl border bg-surface px-3.5 text-sm text-slate-950 shadow-sm transition",
        "placeholder:text-slate-400 focus:border-brand-600 focus:outline-2 focus:outline-offset-1 focus:outline-brand-100",
        "disabled:cursor-not-allowed disabled:bg-subtle disabled:text-slate-500",
        invalid ? "border-danger-600" : "border-border",
        className,
      )}
      aria-invalid={invalid || undefined}
      ref={ref}
      {...props}
    />
  ),
);

Input.displayName = "Input";
