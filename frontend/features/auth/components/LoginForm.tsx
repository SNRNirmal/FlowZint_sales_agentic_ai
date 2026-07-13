"use client"

import { motion } from "framer-motion"
import { ArrowRight, Zap } from "lucide-react"
import { useRouter } from "next/navigation"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { useAuthStore } from "@/store/useAuthStore"

const DEMO_USER = {
  id: "user-001",
  name: "Sales Ops",
  email: "demo@flowzint.com",
  role: "admin",
}

export function LoginForm() {
  const router = useRouter()
  const login = useAuthStore((state) => state.login)

  const enter = () => {
    login(DEMO_USER, "demo-session")
    router.push("/dashboard")
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className="w-full max-w-[400px]"
    >
      <Card className="border-border bg-card shadow-2xl backdrop-blur-sm">
        <CardHeader className="space-y-2">
          <div className="w-9 h-9 rounded-lg bg-primary flex items-center justify-center">
            <Zap className="w-[18px] h-[18px] text-white" />
          </div>
          <CardTitle className="text-2xl font-bold tracking-tight text-foreground">
            Threshold
          </CardTitle>
          <CardDescription className="text-secondary-foreground">
            Internal deal-friction intelligence. Sign in to review what the agents drafted.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button onClick={enter} className="w-full gap-2">
            Enter as Sales Ops
            <ArrowRight className="w-4 h-4" />
          </Button>
        </CardContent>
        <CardFooter className="justify-center text-xs text-muted-foreground">
          Demo mode — no credentials required.
        </CardFooter>
      </Card>
    </motion.div>
  )
}
