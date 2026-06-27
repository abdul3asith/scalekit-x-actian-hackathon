import { db } from "../db";
import { resolveEmployeeAccess } from "../security/scope-resolver";

export async function getEmployeeHours(params: {
  actorEmployeeId: string;
  targetEmployeeId: string;
  startDate: string;
  endDate: string;
}) {
  const scope = await resolveEmployeeAccess({
    actorEmployeeId: params.actorEmployeeId,
    targetEmployeeId: params.targetEmployeeId,
    action: "read_employee_hours",
  });

  if (!scope.allowed) {
    return {
      allowed: false,
      reason: scope.reason,
      data: null,
    };
  }

  const result = await db.query(
    `
    SELECT COALESCE(SUM(total_hours), 0)::float AS total_hours
    FROM time_entries
    WHERE employee_id = $1
      AND clock_in >= $2
      AND clock_out <= $3
    `,
    [params.targetEmployeeId, params.startDate, params.endDate]
  );

  return {
    allowed: true,
    scope: scope.scope,
    data: {
      employee_id: params.targetEmployeeId,
      total_hours: result.rows[0].total_hours,
      start_date: params.startDate,
      end_date: params.endDate,
    },
  };
}

export async function getEmployeeShifts(params: {
  actorEmployeeId: string;
  targetEmployeeId: string;
}) {
  const scope = await resolveEmployeeAccess({
    actorEmployeeId: params.actorEmployeeId,
    targetEmployeeId: params.targetEmployeeId,
    action: "read_employee_shifts",
  });

  if (!scope.allowed) {
    return {
      allowed: false,
      reason: scope.reason,
      data: null,
    };
  }

  const result = await db.query(
    `
    SELECT 
      shifts.id,
      shifts.start_time,
      shifts.end_time,
      shifts.status,
      sites.name AS site_name
    FROM shifts
    LEFT JOIN sites ON shifts.site_id = sites.id
    WHERE shifts.employee_id = $1
    ORDER BY shifts.start_time DESC
    `,
    [params.targetEmployeeId]
  );

  return {
    allowed: true,
    scope: scope.scope,
    data: result.rows,
  };
}