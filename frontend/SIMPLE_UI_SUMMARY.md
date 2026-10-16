# Simple UI Guidelines

To keep the UI professional, simple, and free of unnecessary complexity:

## ✅ Do
- Use only shadcn/ui primitives: Button, Input, Separator, Sheet, Tabs, Tooltip, Sidebar.
- Keep layout simple: flex, grid, spacing (p-, m-, gap-).
- Use static colors: bg-background, text-foreground, border-border.
- Keep typography sensible: text-sm, font-medium, etc.
- Use only essential interactivity: onClick, onChange, value.
- Replace animations with static states (no hover, focus, or transition effects unless critical for accessibility).
- Remove Framer Motion unless absolutely necessary.

## ❌ Avoid
- Hover effects: `hover:bg-*`, `hover:text-*`
- Focus rings: `focus-visible:ring-*`, `focus-visible:outline-*`
- Transitions: `transition-*`, `duration-*`, `ease-*`
- Animation classes: `animate-*`, `data-[state=*]:animate-*`
- Complex components: DropdownMenu, Command, Popover, Toast (use plain alternatives)
- Motion elements: `<motion.div>`, `<motion.tr>`, etc.

## 📝 Example: Simple Button
```tsx
export function Button({ className, ...props }: React.ComponentProps<"button">) {
  return (
    <button
      className={cn(
        "rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground",
        className
      )}
      {...props}
    />
  )
}
```

## 📝 Example: Simple Input
```tsx
export function Input({ className, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      className={cn(
        "rounded-md border border-input bg-background px-3 py-2 text-sm",
        className
      )}
      {...props}
    />
  )
}
```

Apply these principles across the codebase for a clean, professional, and simple UI.