"use client"

import * as React from "react"
import { useRouter } from "next/navigation"
import { useAuthStore } from "@/store/useAuthStore"

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const [checked, setChecked] = React.useState(false)

  React.useEffect(() => {
    if (!isAuthenticated) {
      router.replace("/login")
    } else {
      setChecked(true)
    }
  }, [isAuthenticated, router])

  if (!checked) return null
  return <>{children}</>
}
