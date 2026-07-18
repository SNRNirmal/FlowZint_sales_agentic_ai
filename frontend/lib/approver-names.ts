/**
 * Approver display name mapping.
 *
 * The backend uses system IDs (e.g., "finance_raj") as primary keys.
 * This file maps those IDs to human-readable department labels for display.
 * Department names are used instead of personal names to avoid implying
 * real individuals behind the demo seed data.
 *
 * This is a frontend-only concern. The backend IDs are never changed.
 */

export interface ApproverDisplay {
  label: string
  department: string
  shortCode: string
}

export const APPROVER_DISPLAY: Record<string, ApproverDisplay> = {
  finance_raj: {
    label: "Finance Team",
    department: "Finance",
    shortCode: "FIN",
  },
  legal_jane: {
    label: "Legal Team",
    department: "Legal",
    shortCode: "LEG",
  },
  security_amy: {
    label: "Security Team",
    department: "Security",
    shortCode: "SEC",
  },
  exec_daniel: {
    label: "Executive",
    department: "Executive",
    shortCode: "EXE",
  },
  procurement_li: {
    label: "Procurement Team",
    department: "Procurement",
    shortCode: "PRO",
  },
  compliance_maria: {
    label: "Compliance Team",
    department: "Compliance",
    shortCode: "COM",
  },
}

/** Returns display info for an approver ID; falls back to the raw ID if unknown. */
export function getApproverDisplay(approverId: string): ApproverDisplay {
  return (
    APPROVER_DISPLAY[approverId] ?? {
      label: approverId,
      department: approverId,
      shortCode: approverId.slice(0, 3).toUpperCase(),
    }
  )
}
