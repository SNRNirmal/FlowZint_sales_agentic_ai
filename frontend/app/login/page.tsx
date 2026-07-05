import { Metadata } from "next"
import { LoginForm } from "@/features/auth/components/LoginForm"

export const metadata: Metadata = {
  title: "Login — FlowZint",
  description: "Sign in to your FlowZint workspace",
}

export default function LoginPage() {
  return (
    <div className="relative min-h-screen flex items-center justify-center overflow-hidden bg-background">
      {/* Subtle background glow/noise */}
      <div className="absolute inset-0 z-0">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-primary/10 via-background to-background" />
      </div>

      <div className="relative z-10 w-full px-4 sm:px-0 flex justify-center">
        <LoginForm />
      </div>
    </div>
  )
}
