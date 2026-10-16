import * as React from "react"
import {
  Tooltip as PrimitiveTooltip,
  TooltipProvider as PrimitiveTooltipProvider,
  TooltipTrigger as PrimitiveTooltipTrigger,
  TooltipContent as PrimitiveTooltipContent,
  TooltipArrow as PrimitiveTooltipArrow,
} from "@radix-ui/react-tooltip"
import { cn } from "@/lib/utils"

export const TooltipProvider = PrimitiveTooltipProvider

export const TooltipTrigger = PrimitiveTooltipTrigger

export const TooltipContent = React.forwardRef<
  React.ElementRef<typeof PrimitiveTooltipContent>,
  React.ComponentPropsWithoutRef<typeof PrimitiveTooltipContent> & {
    sideOffset?: number
  }
>(({ className, sideOffset = 4, ...props }, ref) => (
  <PrimitiveTooltipContent
    ref={ref}
    className={cn(
      "z-50 w-[var(--radix-tooltip-width)] max-w-xs rounded-md border border-popover bg-popover px-3 py-2 text-sm text-popover-foreground shadow-lg",
      className
    )}
    sideOffset={sideOffset}
    {...props}
  >
    <PrimitiveTooltipArrow className="fill-popover" />
  </PrimitiveTooltipContent>
))
TooltipContent.displayName = PrimitiveTooltipContent.displayName

// Main Tooltip wrapper that combines trigger and content
export function Tooltip({
  children,
  ...props
}: React.ComponentProps<typeof PrimitiveTooltip>) {
  return (
    <PrimitiveTooltip {...props}>
      {children}
    </PrimitiveTooltip>
  )
}