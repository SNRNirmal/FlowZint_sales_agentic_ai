"use client"

import * as React from "react"
import { Sidebar } from "@/components/layout/Sidebar"
import { TopNav } from "@/components/layout/TopNav"
import { AuthGuard } from "@/components/layout/AuthGuard"
import { Toaster } from "@/components/ui/toaster"

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = React.useState(false)

  return (
    <AuthGuard>
      <div className="flex h-screen w-screen overflow-hidden bg-background">
        <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((c) => !c)} />
        <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
          <TopNav />
          <main className="flex-1 overflow-y-auto">
            <div className="max-w-[1400px] mx-auto px-6 py-6">
              {children}
            </div>
          </main>
        </div>
      </div>
      <Toaster />
    </AuthGuard>
  )
}
