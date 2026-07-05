"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import {
  LayoutDashboard,
  Briefcase,
  ClipboardCheck,
  Brain,
  BarChart3,
  GitBranch,
  Settings,
  Activity,
  ChevronLeft,
  ChevronRight,
  Zap,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"

const NAV_ITEMS = [
  { label: "Dashboard",        href: "/dashboard",  icon: LayoutDashboard },
  { label: "Deals",            href: "/deals",      icon: Briefcase },
  { label: "Human Review",     href: "/review",     icon: ClipboardCheck },
  { label: "Behavioral Twins", href: "/twins",      icon: Brain },
  { label: "Analytics",        href: "/analytics",  icon: BarChart3 },
  { label: "Timeline",         href: "/timeline",   icon: GitBranch },
]

const BOTTOM_ITEMS = [
  { label: "System Health",    href: "/system",     icon: Activity },
  { label: "Settings",         href: "/settings",   icon: Settings },
]

interface SidebarProps {
  collapsed: boolean
  onToggle: () => void
}

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const pathname = usePathname()

  return (
    <TooltipProvider delayDuration={0}>
      <motion.aside
        animate={{ width: collapsed ? 64 : 220 }}
        transition={{ duration: 0.2, ease: "easeInOut" }}
        className="relative flex flex-col h-full bg-card border-r border-border shrink-0 overflow-hidden"
      >
        {/* Logo */}
        <div className="flex items-center h-14 px-4 border-b border-border shrink-0">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-7 h-7 rounded-lg bg-primary flex items-center justify-center shrink-0">
              <Zap className="w-4 h-4 text-white" />
            </div>
            <AnimatePresence>
              {!collapsed && (
                <motion.span
                  initial={{ opacity: 0, width: 0 }}
                  animate={{ opacity: 1, width: "auto" }}
                  exit={{ opacity: 0, width: 0 }}
                  transition={{ duration: 0.15 }}
                  className="font-semibold text-sm tracking-tight text-foreground whitespace-nowrap overflow-hidden"
                >
                  Threshold
                </motion.span>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* Primary Nav */}
        <nav className="flex-1 flex flex-col gap-0.5 p-2 pt-3 overflow-hidden">
          {NAV_ITEMS.map((item) => (
            <NavItem
              key={item.href}
              item={item}
              active={pathname === item.href || pathname.startsWith(item.href + "/")}
              collapsed={collapsed}
            />
          ))}
        </nav>

        {/* Bottom Nav */}
        <div className="flex flex-col gap-0.5 p-2 border-t border-border">
          {BOTTOM_ITEMS.map((item) => (
            <NavItem
              key={item.href}
              item={item}
              active={pathname === item.href}
              collapsed={collapsed}
            />
          ))}

          {/* Collapse toggle */}
          <button
            onClick={onToggle}
            className="flex items-center justify-center w-full h-8 mt-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
          >
            {collapsed
              ? <ChevronRight className="w-4 h-4" />
              : <ChevronLeft className="w-4 h-4" />
            }
          </button>
        </div>
      </motion.aside>
    </TooltipProvider>
  )
}

function NavItem({
  item,
  active,
  collapsed,
}: {
  item: { label: string; href: string; icon: React.ElementType }
  active: boolean
  collapsed: boolean
}) {
  const Icon = item.icon

  const content = (
    <Link
      href={item.href}
      className={cn(
        "flex items-center gap-3 h-9 px-2.5 rounded-md text-sm transition-colors relative group",
        active
          ? "bg-primary/10 text-primary font-medium"
          : "text-muted-foreground hover:text-foreground hover:bg-accent"
      )}
    >
      {active && (
        <motion.div
          layoutId="sidebar-active"
          className="absolute inset-0 rounded-md bg-primary/10"
          transition={{ duration: 0.2, ease: "easeInOut" }}
        />
      )}
      <Icon className={cn("w-4 h-4 shrink-0 relative z-10", active && "text-primary")} />
      <AnimatePresence>
        {!collapsed && (
          <motion.span
            initial={{ opacity: 0, width: 0 }}
            animate={{ opacity: 1, width: "auto" }}
            exit={{ opacity: 0, width: 0 }}
            transition={{ duration: 0.15 }}
            className="whitespace-nowrap overflow-hidden relative z-10"
          >
            {item.label}
          </motion.span>
        )}
      </AnimatePresence>
    </Link>
  )

  if (collapsed) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>{content}</TooltipTrigger>
        <TooltipContent side="right" className="text-xs">
          {item.label}
        </TooltipContent>
      </Tooltip>
    )
  }

  return content
}
