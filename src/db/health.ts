import { Router } from "express";
import { testDbConnection } from "./index";

const router = Router();

router.get("/health/db", async (_req, res) => {
  try {
    const database = await testDbConnection();

    res.json({
      status: "ok",
      database,
    });
  } catch (error) {
    res.status(500).json({
      status: "error",
      message: "Database connection failed",
    });
  }
});

export default router;