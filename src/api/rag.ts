import { Router } from "express";
import { answerWithRag } from "../rag/ragAnswer";

const router = Router();

router.post("/ask", async (req, res) => {
  try {
    const { call_id, question, target_employee_id } = req.body;

    if (!call_id || !question) {
      return res.status(400).json({
        error: "call_id and question are required",
      });
    }

    const result = await answerWithRag({
      callId: call_id,
      question,
      targetEmployeeId: target_employee_id,
    });

    if (!result.allowed) {
      return res.status(result.statusCode || 403).json(result);
    }

    return res.json(result);
  }  catch (error: any) {
    console.error("RAG ask failed:", error);
  
    return res.status(500).json({
      error: "RAG ask failed",
      details: error.message,
    });
  }
  
});

export default router;