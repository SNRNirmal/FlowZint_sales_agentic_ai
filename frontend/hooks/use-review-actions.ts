import { useMutation, useQueryClient } from "@tanstack/react-query"
import { sendApprovalNudge, holdApprovalNudge, resolveApproval } from "@/lib/api"
import type { ResolvePayload } from "@/types/review"

export function useSendNudge() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, text }: { id: string; text: string }) =>
      sendApprovalNudge(id, text),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["deals"] })
      qc.invalidateQueries({ queryKey: ["dashboard"] })
    },
  })
}

export function useHoldNudge() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => holdApprovalNudge(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["deals"] })
    },
  })
}

export function useResolveApproval() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ResolvePayload }) =>
      resolveApproval(id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["deals"] })
      qc.invalidateQueries({ queryKey: ["dashboard"] })
      qc.invalidateQueries({ queryKey: ["twins"] })
    },
  })
}
