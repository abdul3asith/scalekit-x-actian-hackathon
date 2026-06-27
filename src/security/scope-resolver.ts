import { db } from "../db";

type ScopeDecision = {
  allowed: boolean;
  scope: "self" | "manager_site" | "admin" | "blocked";
  reason: string;
};

async function writeAuditLog(params: {
  actorEmployeeId: string;
  action: string;
  resourceType: string;
  resourceId: string;
  decision: "allowed" | "blocked";
  reason: string;
}) {
  await db.query(
    `
    INSERT INTO audit_logs 
    (actor_employee_id, action, resource_type, resource_id, decision, reason)
    VALUES ($1, $2, $3, $4, $5, $6)
    `,
    [
      params.actorEmployeeId,
      params.action,
      params.resourceType,
      params.resourceId,
      params.decision,
      params.reason,
    ]
  );
}

export async function resolveEmployeeAccess(params: {
  actorEmployeeId: string;
  targetEmployeeId: string;
  action?: string;
}): Promise<ScopeDecision> {
  const action = params.action || "read_employee_data";

  const actorResult = await db.query(
    `SELECT id, role, is_active FROM employees WHERE id = $1`,
    [params.actorEmployeeId]
  );

  const targetResult = await db.query(
    `SELECT id, role, is_active FROM employees WHERE id = $1`,
    [params.targetEmployeeId]
  );

  const actor = actorResult.rows[0];
  const target = targetResult.rows[0];

  if (!actor || !actor.is_active) {
    return {
      allowed: false,
      scope: "blocked",
      reason: "Actor employee not found or inactive",
    };
  }

  if (!target || !target.is_active) {
    await writeAuditLog({
      actorEmployeeId: params.actorEmployeeId,
      action,
      resourceType: "employee",
      resourceId: params.targetEmployeeId,
      decision: "blocked",
      reason: "Target employee not found or inactive",
    });

    return {
      allowed: false,
      scope: "blocked",
      reason: "Target employee not found or inactive",
    };
  }

  if (actor.role === "admin") {
    await writeAuditLog({
      actorEmployeeId: params.actorEmployeeId,
      action,
      resourceType: "employee",
      resourceId: params.targetEmployeeId,
      decision: "allowed",
      reason: "Admin can access all employee data",
    });

    return {
      allowed: true,
      scope: "admin",
      reason: "Admin access granted",
    };
  }

  if (params.actorEmployeeId === params.targetEmployeeId) {
    await writeAuditLog({
      actorEmployeeId: params.actorEmployeeId,
      action,
      resourceType: "employee",
      resourceId: params.targetEmployeeId,
      decision: "allowed",
      reason: "Employee accessed own data",
    });

    return {
      allowed: true,
      scope: "self",
      reason: "Self access granted",
    };
  }

  if (actor.role === "manager") {
    const sharedSiteResult = await db.query(
      `
      SELECT 1
      FROM employee_site_access manager_access
      JOIN employee_site_access target_access
        ON manager_access.site_id = target_access.site_id
      WHERE manager_access.employee_id = $1
        AND target_access.employee_id = $2
        AND manager_access.can_work = true
        AND target_access.can_work = true
      LIMIT 1
      `,
      [params.actorEmployeeId, params.targetEmployeeId]
    );

    if (sharedSiteResult.rows.length > 0) {
      await writeAuditLog({
        actorEmployeeId: params.actorEmployeeId,
        action,
        resourceType: "employee",
        resourceId: params.targetEmployeeId,
        decision: "allowed",
        reason: "Manager shares site access with target employee",
      });

      return {
        allowed: true,
        scope: "manager_site",
        reason: "Manager site-level access granted",
      };
    }
  }

  await writeAuditLog({
    actorEmployeeId: params.actorEmployeeId,
    action,
    resourceType: "employee",
    resourceId: params.targetEmployeeId,
    decision: "blocked",
    reason: "Actor is not allowed to access target employee data",
  });

  return {
    allowed: false,
    scope: "blocked",
    reason: "Access denied",
  };
}