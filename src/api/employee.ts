import { Router } from "express";
import { getEmployeeHours, getEmployeeShifts } from "../mal/memoryAccessLayer";
import { getSession } from "../redis/session.store";

const router = Router();

router.get("/:targetEmployeeId/hours", async (req, res) => {
  try {
    const { targetEmployeeId } = req.params;
    const { call_id, start_date, end_date } = req.query;

    if (!call_id || !start_date || !end_date) {
      return res.status(400).json({
        error: "call_id, start_date, and end_date are required",
      });
    }

    const session = await getSession(String(call_id));

    if (!session) {
      return res.status(401).json({ error: "Invalid or expired session" });
    }

    const finalTargetEmployeeId =
      targetEmployeeId === "me" ? session.employee_id : targetEmployeeId;

    const result = await getEmployeeHours({
      actorEmployeeId: session.employee_id,
      targetEmployeeId: finalTargetEmployeeId,
      startDate: String(start_date),
      endDate: String(end_date),
    });

    if (!result.allowed) {
      return res.status(403).json(result);
    }

    return res.json(result);
  } catch (error) {
    console.error("Get employee hours failed:", error);
    return res.status(500).json({ error: "Get employee hours failed" });
  }
});

router.get("/:targetEmployeeId/shifts", async (req, res) => {
  try {
    const { targetEmployeeId } = req.params;
    const { call_id } = req.query;

    if (!call_id) {
      return res.status(400).json({
        error: "call_id is required",
      });
    }

    const session = await getSession(String(call_id));

    if (!session) {
      return res.status(401).json({ error: "Invalid or expired session" });
    }

    const finalTargetEmployeeId =
      targetEmployeeId === "me" ? session.employee_id : targetEmployeeId;

    const result = await getEmployeeShifts({
      actorEmployeeId: session.employee_id,
      targetEmployeeId: finalTargetEmployeeId,
    });

    if (!result.allowed) {
      return res.status(403).json(result);
    }

    return res.json(result);
  } catch (error) {
    console.error("Get employee shifts failed:", error);
    return res.status(500).json({ error: "Get employee shifts failed" });
  }
});

export default router;