import { Router } from "express";
import { db } from "../db";
import { createLeaveRequest } from "../mal/leaveAccessLayer";
import { getEmployeeHours, getEmployeeShifts } from "../mal/memoryAccessLayer";
import { answerWithRag } from "../rag/ragAnswer";
import { createSession, getSession } from "../redis/session.store";

const router = Router();

function extractCallId(body: any) {
    return body.call_id || body.callId || body.call?.id || body.message?.call?.id;
  }
  
  function extractPhone(body: any) {
    return (
      body.phone ||
      body.customer?.number ||
      body.call?.customer?.number ||
      body.message?.customer?.number ||
      body.message?.call?.customer?.number
    );
  }
  
  async function findEmployeeByPhone(phone: string) {
    const result = await db.query(
      `
      SELECT id, full_name, phone, role, scalekit_user_id
      FROM employees
      WHERE regexp_replace(phone, '[^0-9]', '', 'g') =
            regexp_replace($1, '[^0-9]', '', 'g')
      LIMIT 1
      `,
      [phone]
    );
  
    return result.rows[0];
  }

  router.post("/session/start", async (req, res) => {
    try {
      const callId = extractCallId(req.body);
      const phone = extractPhone(req.body);
  
      if (!callId || !phone) {
        return res.status(400).json({
          error: "call_id and phone are required",
        });
      }
  
      const employee = await findEmployeeByPhone(phone);
  
      if (!employee) {
        return res.status(404).json({
          answer: "I could not find an employee account for this phone number.",
        });
      }
  
      const session = await createSession({
        call_id: callId,
        employee_id: employee.id,
        scalekit_user_id: employee.scalekit_user_id,
        role: employee.role,
        state: {
          phone,
          employee_name: employee.full_name,
        },
      });
  
      return res.json({
        answer: `Hi ${employee.full_name}, I verified your employee account. How can I help with your schedule today?`,
        session,
      });
    } catch (error: any) {
      console.error("Vapi session start failed:", error);
  
      return res.status(500).json({
        error: "Vapi session start failed",
        details: error.message,
      });
    }
  });
  
router.post("/tool", async (req, res) => {
  try {
    const { call_id, action, input } = req.body;

    if (!call_id || !action) {
      return res.status(400).json({
        error: "call_id and action are required",
      });
    }

    const session = await getSession(call_id);

    if (!session) {
      return res.status(401).json({
        error: "Invalid or expired session",
      });
    }

    if (action === "get_hours") {
      const result = await getEmployeeHours({
        actorEmployeeId: session.employee_id,
        targetEmployeeId: input?.target_employee_id || session.employee_id,
        startDate: input?.start_date,
        endDate: input?.end_date,
      });

      return res.json({
        answer: result.allowed
          ? `You worked ${result.data?.total_hours} hours.`
          : result.reason,
        result,
      });
    }

    if (action === "get_shifts") {
      const result = await getEmployeeShifts({
        actorEmployeeId: session.employee_id,
        targetEmployeeId: input?.target_employee_id || session.employee_id,
      });

      return res.json({
        answer: result.allowed
          ? `I found ${result.data?.length || 0} shifts.`
          : result.reason,
        result,
      });
    }

    if (action === "ask_memory") {
      const result = await answerWithRag({
        callId: call_id,
        question: input?.question,
        targetEmployeeId: input?.target_employee_id,
      });

      return res.json({
        answer: result.answer || result.error,
        result,
      });
    }
    if (action === "request_leave") {
        const result = await createLeaveRequest({
          actorEmployeeId: session.employee_id,
          targetEmployeeId: input?.target_employee_id || session.employee_id,
          startTime: input?.start_time,
          endTime: input?.end_time,
          reason: input?.reason,
          emergency: false,
        });
      
        return res.json({
          answer: result.allowed
            ? "Your leave request has been submitted and is pending approval."
            : result.reason,
          result,
        });
      }
      
      if (action === "emergency_leave") {
        const result = await createLeaveRequest({
          actorEmployeeId: session.employee_id,
          targetEmployeeId: input?.target_employee_id || session.employee_id,
          startTime: input?.start_time,
          endTime: input?.end_time,
          reason: input?.reason || "Emergency leave",
          emergency: true,
        });
      
        return res.json({
          answer: result.allowed
            ? result.data?.needs_reassignment
              ? "Your emergency leave has been recorded. Your affected shift needs reassignment."
              : "Your emergency leave has been recorded."
            : result.reason,
          result,
        });
      }
    return res.status(400).json({
      error: "Unknown action",
    });
  } catch (error: any) {
    console.error("Vapi tool failed:", error);

    return res.status(500).json({
      error: "Vapi tool failed",
      details: error.message,
    });
  }
});

export default router;