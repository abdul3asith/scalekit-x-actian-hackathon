import { connectRedis, redisClient } from "./redis.client";

export type VoiceSession = {
  call_id: string;
  employee_id: string;
  scalekit_user_id?: string;
  role: "employee" | "manager" | "admin";
  state?: Record<string, unknown>;
};

const SESSION_TTL_SECONDS = 60 * 60;

export async function createSession(session: VoiceSession) {
  await connectRedis();

  await redisClient.set(
    `voice_session:${session.call_id}`,
    JSON.stringify(session),
    {
      EX: SESSION_TTL_SECONDS,
    }
  );

  return session;
}

export async function getSession(callId: string) {
  await connectRedis();

  const raw = await redisClient.get(`voice_session:${callId}`);

  if (!raw) return null;

  return JSON.parse(raw) as VoiceSession;
}

export async function deleteSession(callId: string) {
  await connectRedis();

  await redisClient.del(`voice_session:${callId}`);

  return { deleted: true };
}