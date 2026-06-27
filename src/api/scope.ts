import { Router } from "express";
import { resolveEmployeeAccess } from "../security/scope-resolver";

const router = Router();

router.post("/check", async (req, res) => {
  try {
    const { actor_employee_id, target_employee_id, action } = req.body;

    if (!actor_employee_id || !target_employee_id) {
      return res.status(400).json({
        error: "actor_employee_id and target_employee_id are required",
      });
    }

    const decision = await resolveEmployeeAccess({
      actorEmployeeId: actor_employee_id,
      targetEmployeeId: target_employee_id,
      action,
    });

    return res.json(decision);
  } catch (error) {
    console.error("Scope check failed:", error);

    return res.status(500).json({
      error: "Scope check failed",
    });
  }
});

export default router;