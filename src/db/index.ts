import { Pool } from "pg";

export const db = new Pool({
  connectionString: process.env.DATABASE_URL,
});

export async function testDbConnection() {
  const result = await db.query("SELECT current_database()");
  return result.rows[0].current_database;
}