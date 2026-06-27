import { db } from "../db";
import { resolveEmployeeAccess } from "../security/scope-resolver";

export async function secureSearchEmployeeMemory(params: {
  actorEmployeeId: string;
  targetEmployeeId: string;
  query: string;
}) {
  const scope = await resolveEmployeeAccess({
    actorEmployeeId: params.actorEmployeeId,
    targetEmployeeId: params.targetEmployeeId,
    action: "read_employee_memory",
  });

  if (!scope.allowed) {
    return {
      allowed: false,
      reason: scope.reason,
      data: null,
    };
  }

  const keywords = params.query
  .toLowerCase()
  .split(/\s+/)
  .filter((word) => word.length > 3)
  .map((word) => `%${word}%`);

const result = await db.query(
  `
  SELECT 
    id,
    employee_id,
    site_id,
    memory_type,
    content,
    metadata,
    created_at
  FROM memory_records
  WHERE employee_id = $1
    AND (
      $2::text[] = '{}'
      OR content ILIKE ANY($2::text[])
    )
  ORDER BY created_at DESC
  LIMIT 10
  `,
  [params.targetEmployeeId, keywords]
);

  return {
    allowed: true,
    scope: scope.scope,
    data: result.rows,
  };
}

export async function createEmployeeMemory(params: {
  employeeId: string;
  siteId?: string;
  memoryType: string;
  content: string;
  metadata?: Record<string, unknown>;
}) {
  const result = await db.query(
    `
    INSERT INTO memory_records
    (employee_id, site_id, memory_type, content, metadata)
    VALUES ($1, $2, $3, $4, $5)
    RETURNING *
    `,
    [
      params.employeeId,
      params.siteId || null,
      params.memoryType,
      params.content,
      JSON.stringify(params.metadata || {}),
    ]
  );

  return result.rows[0];
}