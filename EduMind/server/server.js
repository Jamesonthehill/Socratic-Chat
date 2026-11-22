const express = require("express");
const cors = require("cors");
const app = express();
const PORT = 3000;

app.use(
  cors({
    origin: (origin, callback) => {
      const allowedOrigins = [
        "http://localhost:80",
        "http://localhost",
        "http://localhost:5173",
        /\.ngrok\.io$/,
        /\.ngrok-free\.app$/,
      ];

      if (!origin) return callback(null, true); // Allow non-browser tools like Postman

      const isAllowed = allowedOrigins.some((allowed) =>
        typeof allowed === "string" ? allowed === origin : allowed.test(origin)
      );

      if (isAllowed) {
        callback(null, true);
      } else {
        callback(new Error("Not allowed by CORS"));
      }
    },
    credentials: true,
  })
);

app.use(express.json());

// Routes
app.use("/api/v1/users", require("./routes/user"));
app.use("/api/v1/teams", require("./routes/team"));
app.use("/api/v1/user-teams", require("./routes/userTeam"));
app.use("/api/v1/project", require("./routes/project"));
app.use("/api/v1/graph", require("./routes/graph"));
app.use("/api/v1/chat", require("./routes/message"));
app.use("/api/v1/session", require("./routes/session"));
app.use("/api/v1/question", require("./routes/question"));

app.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
});
