export type QuotaState = "metered" | "unlimited" | "unknown" | "unavailable";
export type FetchState = "ok" | "stale" | "error";

export interface LimitWindow {
  window_id: string;
  name: string;
  quota_state: QuotaState;
  used_pct: number | null;
  resets_at: string | null;
  resets_in_seconds: number | null;
  estimated: boolean;
  temporary: boolean;
  inferred: boolean;
  status_note: string | null;
}

export interface CapacityNotice {
  notice_id: string;
  kind: string;
  title: string;
  message: string;
  temporary: boolean;
  inferred: boolean;
  confidence: string;
  evidence: string | null;
}

export interface Provider {
  id: string;
  label: string;
  kind: string;
  support_tier: "stable" | "beta" | "experimental";
  data_source: string;
  auth: { status: string; expires_at: string | null; reauth?: { command?: string | null; automatable?: boolean } | null };
  windows: LimitWindow[];
  capacity_notices: CapacityNotice[];
  fetch_status: FetchState;
  fetch_error: { message: string; user_action?: string | null } | null;
  last_success_at: string | null;
}

export interface Snapshot {
  generated_at: string;
  providers: Provider[];
  advisor: {
    suggestion: string | null;
    ranking: Array<{ id: string; score: number; reason: string; excluded: boolean }>;
    expiring_unused: Array<{
      id: string;
      window: string;
      unused_pct: number;
      resets_at: string;
      note: string;
    }>;
  };
}
