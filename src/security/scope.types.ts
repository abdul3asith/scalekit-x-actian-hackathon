export type Role = "employee" | "supervisor" | "manager" | "admin";

export type AccessDecisionType = "ALLOW" | "DENY" | "STEP_UP" | "REDACT";

export type Actor = {
  tenantId: string;
  employeeId: string;
  role: Role;
  siteIds: string[];
  authLevel: "phone_verified" | "pin_verified" | "otp_verified";
};

export type AccessRequest = {
  callId: string;
  actor: Actor;
  intent: string;
  resource: string;
  operation: "read" | "write";
  target?: {
    employeeId?: string;
    shiftId?: string;
    siteId?: string;
  };
};

export type AccessDecision = {
  decision: AccessDecisionType;
  filters: Record<string, unknown>;
  redactions: string[];
  reason: string;
};
