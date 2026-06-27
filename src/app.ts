import express from "express";
import scopeRouter from "./api/scope";
import dbHealthRouter from "./db/health";

const app = express();

app.use(express.json());

app.get("/", (_req, res) => {
  res.json({ status: "running" });
});

app.use(dbHealthRouter);
app.use("/scope", scopeRouter);

export default app;