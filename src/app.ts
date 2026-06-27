import express from "express";
import cors from "cors";
import dotenv from "dotenv";

dotenv.config();

export const app = express();

app.use(cors());
app.use(express.json());

app.get("/health", (_req, res) => {
  res.json({
    status: "ok",
    service: "security-voice-agent",
  });
});

// Vapi webhook
app.post("/vapi/webhook", (_req, res) => {
  res.json({ received: true });
});

// Tool endpoints
app.post("/tools/get-my-hours", (_req, res) => {
  res.json({ message: "get-my-hours stub" });
});

app.post("/tools/get-my-shifts", (_req, res) => {
  res.json({ message: "get-my-shifts stub" });
});

app.post("/tools/request-emergency-leave", (_req, res) => {
  res.json({ message: "request-emergency-leave stub" });
});

app.post("/tools/request-shift-swap", (_req, res) => {
  res.json({ message: "request-shift-swap stub" });
});

app.post("/tools/ask-policy", (_req, res) => {
  res.json({ message: "ask-policy stub" });
});
