import { db } from "../db";
import { resolveEmployeeAccess } from "../security/scope-resolver";

export async function createLeaveRequest(params: {
  actorEmployeeId: string;
  targetEmployeeId: string;
  startTime: string;
  endTime: string;
  reason?: string;
  emergency?: boolean;
}) {
  const scope = await resolveEmployeeAccess({
    actorEmployeeId: params.actorEmployeeId,
    targetEmployeeId: params.targetEmployeeId,
    action: params.emergency ? "create_emergency_leave" : "create_leave_request",
  });

  if (!scope.allowed) {
    return {
      allowed: false,
      reason: scope.reason,
      data: null,
    };
  }

  const status = params.emergency ? "emergency" : "pending";

  const leaveResult = await db.query(
    `
    INSERT INTO leave_requests
    (employee_id, start_time, end_time, reason, status)
    VALUES ($1, $2, $3, $4, $5)
    RETURNING *
    `,
    [
      params.targetEmployeeId,
      params.startTime,
      params.endTime,
      params.reason || null,
      status,
    ]
  );

  const affectedShifts = await db.query(
    `
    SELECT id, employee_id, site_id, start_time, end_time, status
    FROM shifts
    WHERE employee_id = $1
      AND status = 'scheduled'
      AND start_time < $3
      AND end_time > $2
    ORDER BY start_time ASC
    `,
    [params.targetEmployeeId, params.startTime, params.endTime]
  );

  return {
    allowed: true,
    scope: scope.scope,
    data: {
      leave_request: leaveResult.rows[0],
      affected_shifts: affectedShifts.rows,
      needs_reassignment: params.emergency && affectedShifts.rows.length > 0,
    },
  };
}