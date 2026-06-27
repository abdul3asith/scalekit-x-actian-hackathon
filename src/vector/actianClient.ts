import {
    VectorAIClient,
    type VectorAIClientOptions,
} from "@actian/vectorai-client";
  
  export const ACTIAN_COLLECTION_PREFIX =
    process.env.ACTIAN_VECTOR_COLLECTION || "employee_memory";
  
  const options: VectorAIClientOptions = {
    restUrl: process.env.ACTIAN_VECTORAI_REST || "http://localhost:6573",
    timeout: 30,
    maxRetries: 3,
  };
  
  if (process.env.ACTIAN_VECTORAI_ACCESS_TOKEN) {
    options.accessToken = process.env.ACTIAN_VECTORAI_ACCESS_TOKEN;
  }
  
  export const actianClient = new VectorAIClient(
    process.env.ACTIAN_VECTORAI_GRPC || "localhost:6574",
    options
  );
  
  export function getEmployeeMemoryCollection(employeeId: string) {
    return `${ACTIAN_COLLECTION_PREFIX}_${employeeId.replace(/-/g, "_")}`;
  }
  
  export async function ensureActianCollection(
    collectionName: string,
    dimension: number
  ) {
    try {
      await actianClient.collections.create(collectionName, {
        dimension,
        distanceMetric: "COSINE",
      });
  
      console.log(`Actian collection created: ${collectionName}`);
    } catch (error: any) {
      const message = String(error?.message || error);
  
      if (
        message.toLowerCase().includes("already") ||
        message.toLowerCase().includes("exists")
      ) {
        return;
      }
  
      throw error;
    }
  }