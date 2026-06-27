import { Router } from "express";
import { getSession } from "../redis/session.store";
import {
    createActianEmployeeMemory,
    secureSearchActianEmployeeMemory
} from "../vector/secureActianMemory";

const router = Router();

router.get("/search", async (req, res) => {
  try {
    const { call_id, q, target_employee_id } = req.query;

    if (!call_id || !q) {
      return res.status(400).json({
        error: "call_id and q are required",
      });
    }

    const session = await getSession(String(call_id));

    if (!session) {
      return res.status(401).json({
        error: "Invalid or expired session",
      });
    }

    const targetEmployeeId = target_employee_id
      ? String(target_employee_id)
      : session.employee_id;

      const result = await secureSearchActianEmployeeMemory({
        actorEmployeeId: session.employee_id,
        targetEmployeeId,
        query: String(q),
      });

    if (!result.allowed) {
      return res.status(403).json(result);
    }

    return res.json(result);
  } catch (error: any) {
    console.error("Memory search failed:", error);
  
    return res.status(500).json({
      error: "Memory search failed",
      details: error.message,
    });
  }
});

router.post("/", async (req, res) => {
  try {
    const { employee_id, site_id, memory_type, content, metadata } = req.body;

    if (!employee_id || !memory_type || !content) {
      return res.status(400).json({
        error: "employee_id, memory_type, and content are required",
      });
    }

    const memory = await createActianEmployeeMemory({
        employeeId: employee_id,
        siteId: site_id,
        memoryType: memory_type,
        content,
        metadata,
      });

    return res.json({
      status: "created",
      memory,
    });
  } catch (error) {
    console.error("Create memory failed:", error);
    return res.status(500).json({
      error: "Create memory failed",
    });
  }
});

export default router;