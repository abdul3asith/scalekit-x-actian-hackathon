import express from "express";
import employeeRouter from "./api/employee";
import memoryRouter from "./api/memory";
import ragRouter from "./api/rag";
import scopeRouter from "./api/scope";
import sessionRouter from "./api/session";
import vapiRouter from "./api/vapi";
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
app.use("/memory", memoryRouter);
app.use("/rag", ragRouter)
app.use("/vapi", vapiRouter);

export default app;