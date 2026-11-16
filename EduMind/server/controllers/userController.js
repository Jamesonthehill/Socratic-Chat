const db = require("../db");
const { v4: uuidv4 } = require("uuid");

exports.createUser = async (req, res) => {
  const userId = uuidv4();
  const { username, password, email, full_name } = req.body;
  const [result] = await db.execute(
    "INSERT INTO users (id, username, password, email, full_name) VALUES (?, ?, ?, ?, ?)",
    [userId, username, password, email, full_name]
  );
  res.status(201).json({ id: userId });
};

exports.getAllUsers = async (req, res) => {
  const [rows] = await db.execute("SELECT * FROM users");
  res.json(rows);
};

exports.getUser = async (req, res) => {
  const [rows] = await db.execute("SELECT * FROM users WHERE id = ?", [
    req.params.id,
  ]);
  res.json(rows[0]);
};

exports.updateUser = async (req, res) => {
  const { full_name } = req.body;
  await db.execute(
    "UPDATE users SET full_name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
    [full_name, req.params.id]
  );
  res.json({ message: "User updated" });
};

exports.deleteUser = async (req, res) => {
  await db.execute("DELETE FROM users WHERE id = ?", [req.params.id]);
  res.json({ message: "User deleted" });
};
