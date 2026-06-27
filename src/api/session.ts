import { Router } from "express";
import { createSession, deleteSession, getSession } from "../redis/session.store";

const router = Router();

router.post("/", async (req, res) => {
  try {
    const session = await createSession(req.body);
    return res.json({ status: "created", session });
  } catch (error) {
    console.error("Create session failed:", error);
    return res.status(500).json({ error: "Create session failed" });
  }
});

router.get("/:callId", async (req, res) => {
  try {
    const session = await getSession(req.params.callId);

    if (!session) {
      return res.status(404).json({ error: "Session not found" });
    }

    return res.json(session);
  } catch (error) {
    console.error("Get session failed:", error);
    return res.status(500).json({ error: "Get session failed" });
  }
});

router.delete("/:callId", async (req, res) => {
  try {
    const result = await deleteSession(req.params.callId);
    return res.json(result);
  } catch (error) {
    console.error("Delete session failed:", error);
    return res.status(500).json({ error: "Delete session failed" });
  }
});

export default router;