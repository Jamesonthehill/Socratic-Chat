const db = require("../db");
const { v4: uuidv4 } = require("uuid");

exports.createTeam = async (req, res) => {
  const { name, description } = req.body;
  const teamId = uuidv4();

  await db.execute(
    "INSERT INTO teams (id, name, description) VALUES (?, ?, ?)",
    [teamId, name, description]
  );

  res.status(201).json({ id: teamId });
};

exports.getAllTeams = async (req, res) => {
  const [rows] = await db.execute("SELECT * FROM teams");
  res.json(rows);
};

exports.getTeam = async (req, res) => {
  const [rows] = await db.execute("SELECT * FROM teams WHERE id = ?", [
    req.params.id,
  ]);
  res.json(rows[0]);
};

exports.updateTeam = async (req, res) => {
  const { description } = req.body;
  await db.execute("UPDATE teams SET description = ? WHERE id = ?", [
    description,
    req.params.id,
  ]);
  res.json({ message: "Team updated" });
};

exports.deleteTeam = async (req, res) => {
  await db.execute("DELETE FROM teams WHERE id = ?", [req.params.id]);
  res.json({ message: "Team deleted" });
};
