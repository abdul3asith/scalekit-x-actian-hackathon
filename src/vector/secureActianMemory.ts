import { randomUUID } from "crypto";

import { embedText } from "../llm/embeddings";
import { resolveEmployeeAccess } from "../security/scope-resolver";
import {
    actianClient,
    ensureActianCollection,
    getEmployeeMemoryCollection,
} from "./actianClient";

export async function createActianEmployeeMemory(params: {
  employeeId: string;
  siteId?: string;
  memoryType: string;
  content: string;
  metadata?: Record<string, unknown>;
}) {
  const vector = await embedText(params.content);

  if (!vector || vector.length === 0) {
    throw new Error("Embedding generation failed");
  }

  const collectionName = getEmployeeMemoryCollection(params.employeeId);

  await ensureActianCollection(collectionName, vector.length);

  const id = randomUUID();

  await actianClient.points.upsert(
    collectionName,
    [
      {
        id,
        vector,
        payload: {
          id,
          employee_id: params.employeeId,
          site_id: params.siteId || null,
          memory_type: params.memoryType,
          content: params.content,
          metadata: params.metadata || {},
          created_at: new Date().toISOString(),
        },
      },
    ],
    { wait: true }
  );

  return {
    id,
    employee_id: params.employeeId,
    site_id: params.siteId || null,
    memory_type: params.memoryType,
    content: params.content,
    metadata: params.metadata || {},
    collection: collectionName,
  };
}

export async function secureSearchActianEmployeeMemory(params: {
  actorEmployeeId: string;
  targetEmployeeId: string;
  query: string;
  limit?: number;
}) {
  const scope = await resolveEmployeeAccess({
    actorEmployeeId: params.actorEmployeeId,
    targetEmployeeId: params.targetEmployeeId,
    action: "read_employee_vector_memory",
  });

  if (!scope.allowed) {
    return {
      allowed: false,
      reason: scope.reason,
      data: null,
    };
  }

  const queryVector = await embedText(params.query);

  if (!queryVector || queryVector.length === 0) {
    throw new Error("Query embedding generation failed");
  }

  const collectionName = getEmployeeMemoryCollection(params.targetEmployeeId);

  await ensureActianCollection(collectionName, queryVector.length);

  const results = await actianClient.points.search(
    collectionName,
    queryVector,
    {
      limit: params.limit || 10,
    }
  );

  return {
    allowed: true,
    scope: scope.scope,
    data: results.map((result: any) => ({
      id: result.id,
      score: result.score,
      ...result.payload,
    })),
  };
}