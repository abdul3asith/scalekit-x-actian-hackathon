import { app } from "./app";

const PORT = process.env.PORT || 4000;

app.listen(PORT, () => {
  console.log(`Security voice agent backend running on port ${PORT}`);
});
