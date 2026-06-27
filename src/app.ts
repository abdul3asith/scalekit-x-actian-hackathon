import express from "express";
import employeeRouter from "./api/employee";
import scopeRouter from "./api/scope";
import sessionRouter from "./api/session";
import dbHealthRouter from "./db/health";
const app = express();

app.use(express.json());

app.get("/", (_req, res) => {
  res.json({ status: "running" });
});

app.use(dbHealthRouter);
app.use("/scope", scopeRouter);
app.use("/employees", employeeRouter)
app.use("/sessions", sessionRouter);

export default app;