export const queryKeys = {
  dashboard: ["dashboard"] as const,
  analytics: ["analytics"] as const,
  deals: ["deals"] as const,
  deal: (id: string) => ["deal", id] as const,
  dealPrefix: ["deal"] as const,
  timeline: (id: string) => ["timeline", id] as const,
  twins: ["twins"] as const,
  pendingApprovals: ["approvals", "pending"] as const,
  allApprovals: ["approvals", "all"] as const,
}
