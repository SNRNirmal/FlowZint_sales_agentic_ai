import { Metadata } from "next"

export const metadata: Metadata = {
  title: "Analytics — FlowZint",
  description: "Detailed analytics and reports",
}

export default function AnalyticsPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-foreground">
            Analytics & Reports
          </h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Deep dive into pipeline metrics and behavioral twin performance.
          </p>
        </div>
      </div>
      
      <div className="bg-card border border-border rounded-xl p-12 text-center shadow-sm">
        <h2 className="text-lg font-medium text-foreground mb-2">Coming Soon</h2>
        <p className="text-sm text-muted-foreground max-w-md mx-auto">
          The comprehensive analytics dashboard is currently under construction. 
          Check back later for detailed reports on deal velocity, approval bottlenecks, and AI prediction accuracy.
        </p>
      </div>
    </div>
  )
}
