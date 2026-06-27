import { askNebius } from "../llm/nebiusClient";
import { getSession } from "../redis/session.store";
import { secureSearchActianEmployeeMemory } from "../vector/secureActianMemory";

export async function answerWithRag(params: {
  callId: string;
  question: string;
  targetEmployeeId?: string;
}) {
  const session = await getSession(params.callId);

  if (!session) {
    return {
      allowed: false,
      statusCode: 401,
      error: "Invalid or expired session",
    };
  }

  const targetEmployeeId = params.targetEmployeeId || session.employee_id;

  const memoryResult = await secureSearchActianEmployeeMemory({
    actorEmployeeId: session.employee_id,
    targetEmployeeId,
    query: params.question,
  });

  if (!memoryResult.allowed) {
    return {
      allowed: false,
      statusCode: 403,
      error: memoryResult.reason,
    };
  }

  const memories = memoryResult.data || [];

  if (memories.length === 0) {
    return {
      allowed: true,
      answer: "I do not have enough authorized memory to answer that.",
      memories: [],
    };
  }

  const context = memories
    .map((m: any, index: number) => {
      return `Memory ${index + 1}: ${m.content}`;
    })
    .join("\n");

  const answer = await askNebius([
    {
      role: "system",
      content:
        "You are a secure scheduling voice assistant. Answer only using the authorized context provided. Do not reveal data from other employees. If the context is insufficient, say you do not have enough authorized information.",
    },
    {
      role: "user",
      content: `
Authorized context:
${context}

User question:
${params.question}
      `,
    },
  ]);

  return {
    allowed: true,
    answer,
    memories,
  };
}