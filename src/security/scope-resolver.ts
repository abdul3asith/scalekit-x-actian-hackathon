import { AccessDecision, AccessRequest } from "./scope.types";

export function resolveScope(request: AccessRequest): AccessDecision {
  const { actor, target, resource, operation } = request;

  const targetEmployeeId = target?.employeeId || actor.employeeId;

  if (actor.role === "employee") {
    if (targetEmployeeId !== actor.employeeId) {
      return {
        decision: "DENY",
        filters: {},
        redactions: [],
        reason: "Employee cannot access another employee's data.",
      };
    }

    return {
      decision: "ALLOW",
      filters: {
        tenant_id: actor.tenantId,
        employee_id: actor.employeeId,
      },
      redactions: [],
      reason: "Employee can access their own data.",
    };
  }

  if (actor.role === "manager" || actor.role === "admin") {
    return {
      decision: "ALLOW",
      filters: {
        tenant_id: actor.tenantId,
      },
      redactions: [],
      reason: `${actor.role} can access tenant-scoped ${resource} data.`,
    };
  }

  if (actor.role === "supervisor") {
    return {
      decision: "ALLOW",
      filters: {
        tenant_id: actor.tenantId,
        site_ids: actor.siteIds,
      },
      redactions: operation === "read" ? [] : ["payroll_sensitive_fields"],
      reason: "Supervisor can access assigned site data.",
    };
  }

  return {
    decision: "DENY",
    filters: {},
    redactions: [],
    reason: "Unknown role or unsupported access request.",
  };
}
