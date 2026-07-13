import { useMutation, useQueryClient, type QueryClient } from "@tanstack/react-query"
import { sendApprovalNudge, holdApprovalNudge, resolveApproval } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"
import type { ResolvePayload } from "@/types/review"

function invalidateDealData(qc: QueryClient) {
  qc.invalidateQueries({ queryKey: queryKeys.dashboard })
  qc.invalidateQueries({ queryKey: queryKeys.deals })
  qc.invalidateQueries({ queryKey: queryKeys.dealPrefix })
  qc.invalidateQueries({ queryKey: queryKeys.pendingApprovals })
}

export function useSendNudge() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, text }: { id: string; text: string }) => sendApprovalNudge(id, text),
    onSuccess: () => invalidateDealData(qc),
  })
}

export function useHoldNudge() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => holdApprovalNudge(id),
    onSuccess: () => invalidateDealData(qc),
  })
}

// Deliberately no onSuccess invalidation here: invalidating dealPrefix would
// refetch the open deal-detail query, flip the approval to "approved", and the
// status-gated ResolveDialog would unmount while its success panel is showing.
// The modal blocks page interaction while open, so staleness is invisible until
// close — the dialog calls useResolveInvalidation() when it closes instead.
export function useResolveApproval() {
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ResolvePayload }) => resolveApproval(id, payload),
  })
}

// Invalidates everything a recorded outcome touches (deal data + twins).
// Called by ResolveDialog on close after a successful resolve — see the
// comment on useResolveApproval for why this is deferred.
export function useResolveInvalidation() {
  const qc = useQueryClient()
  return () => {
    invalidateDealData(qc)
    qc.invalidateQueries({ queryKey: queryKeys.twins })
  }
}
