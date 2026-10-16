import * as React from "react"
import { cn } from "@/lib/utils"

export interface SeparatorProps extends React.HTMLAttributes<HTMLHRElement> {
  orientation?: "horizontal" | "vertical"
}

export function Separator({
  className,
  orientation = "horizontal",
  ...props
}: SeparatorProps) {
  return orientation === "vertical" ? (
    <div className={cn("h-5 w-px bg-border", className)} {...props} />
  ) : (
    <hr className={cn("my-2 h-px bg-border", className)} {...props} />
  )
}