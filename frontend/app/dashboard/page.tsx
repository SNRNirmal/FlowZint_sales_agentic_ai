import { Metadata } from "next"

export const metadata: Metadata = {
  title: "Dashboard — FlowZint",
}

export default function DashboardPage() {
  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center p-8">
      <h1 className="text-3xl font-bold tracking-tight text-foreground">Dashboard</h1>
      <p className="mt-2 text-secondary-foreground">Welcome to FlowZint.</p>
    </div>
  )
}
