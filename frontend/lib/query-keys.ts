export const queryKeys = {
  dashboard: ["dashboard"] as const,
  deals: ["deals"] as const,
  deal: (id: string) => ["deal", id] as const,
  dealPrefix: ["deal"] as const,
  twins: ["twins"] as const,
  pendingApprovals: ["approvals", "pending"] as const,
}
