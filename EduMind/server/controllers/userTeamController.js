const db = require("../db");

exports.createUserTeam = async (req, res) => {
  const { user_id, team_id } = req.body;
  await db.execute("INSERT INTO user_teams (user_id, team_id) VALUES (?, ?)", [
    user_id,
    team_id,
  ]);
  res.json({ message: "User added to team" });
};

exports.getUserTeam = async (req, res) => {
  const [rows] = await db.execute(
    "SELECT * FROM user_teams WHERE user_id = ? AND team_id = ?",
    [req.params.user_id, req.params.team_id]
  );
  res.json(rows[0]);
};

exports.deleteUserTeam = async (req, res) => {
  await db.execute("DELETE FROM user_teams WHERE user_id = ? AND team_id = ?", [
    req.params.user_id,
    req.params.team_id,
  ]);
  res.json({ message: "User removed from team" });
};

exports.getTeamsByUserId = async (req, res) => {
  const userId = req.params.user_id;

  try {
    const [rows] = await db.execute(
      `
      SELECT t.id, t.name, t.description, t.created_at
      FROM user_teams ut
      JOIN teams t ON ut.team_id = t.id
      WHERE ut.user_id = ?
      ORDER BY t.name
      `,
      [userId]
    );

    res.json({ teams: rows });
  } catch (error) {
    console.error("Error fetching user teams:", error);
    res.status(500).json({ error: "Failed to fetch teams for user" });
  }
};
