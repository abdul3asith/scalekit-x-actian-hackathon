import express from "express";
import dbHealthRouter from "./db/health";

const app = express();

app.use(express.json());

app.get("/", (_req, res) => {
  res.json({ status: "running" });
});

app.use(dbHealthRouter);

export default app;