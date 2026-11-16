const db = require("../db");
const { v4: uuidv4 } = require("uuid");

exports.getAllGraphs = async (req, res) => {
  try {
    const [rows] = await db.execute(
      "SELECT * FROM edumind.graphs ORDER BY created_at DESC"
    );
    res.json({ graphs: rows });
  } catch (err) {
    res.status(500).json({ error: "Failed to fetch graphs" });
  }
};

exports.getGraphById = async (req, res) => {
  try {
    const [rows] = await db.execute(
      "SELECT * FROM edumind.graphs WHERE id = ?",
      [req.params.id]
    );
    if (rows.length === 0)
      return res.status(404).json({ error: "Graph not found" });
    res.json(rows[0]);
  } catch (err) {
    res.status(500).json({ error: "Failed to fetch graph" });
  }
};

exports.getGraphsByUserId = async (req, res) => {
  try {
    const [rows] = await db.execute(
      `SELECT g.id, g.name, t.name as team, u.full_name as owner, g.created_at, g.updated_at, g.status
          FROM edumind.graphs g
          LEFT JOIN edumind.teams t ON g.team_id = t.id
          LEFT JOIN edumind.users u ON g.user_id = u.id
          WHERE u.id = ?`,
      [req.params.userId]
    );
    res.json({ graphs: rows });
  } catch (err) {
    res.status(500).json({ error: "Failed to fetch graphs for user" });
  }
};

exports.getGraphsByTeamId = async (req, res) => {
  try {
    const [rows] = await db.execute(
      "SELECT * FROM edumind.graphs WHERE team_id = ? ORDER BY created_at DESC",
      [req.params.teamId]
    );
    res.json({ graphs: rows });
  } catch (err) {
    res.status(500).json({ error: "Failed to fetch graphs for team" });
  }
};

exports.createGraph = async (req, res) => {
  const { name, user_id, team_id, scheduled_at } = req.body;
  if (!name || !user_id || !team_id) {
    return res.status(400).json({ error: "Missing required fields" });
  }

  const graphId = uuidv4();

  try {
    await db.execute(
      `INSERT INTO edumind.graphs (id, name, user_id, team_id, scheduled_at)
       VALUES (?, ?, ?, ?, ?)`,
      [graphId, name, user_id, team_id, scheduled_at || null]
    );
    res.status(201).json({ id: graphId });
  } catch (err) {
    res.status(500).json({ error: "Failed to create graph" });
  }
};

exports.updateGraph = async (req, res) => {
  const { name, status, scheduled_at, completed_at, error_message } = req.body;
  try {
    const [result] = await db.execute(
      `UPDATE edumind.graphs
       SET name = ?, status = ?, scheduled_at = ?, completed_at = ?, error_message = ?, updated_at = CURRENT_TIMESTAMP
       WHERE id = ?`,
      [
        name,
        status,
        scheduled_at || null,
        completed_at || null,
        error_message || null,
        req.params.id,
      ]
    );
    res.json({ updated: result.affectedRows });
  } catch (err) {
    res.status(500).json({ error: "Failed to update graph" });
  }
};

exports.deleteGraph = async (req, res) => {
  try {
    const [result] = await db.execute(
      "DELETE FROM edumind.graphs WHERE id = ?",
      [req.params.id]
    );
    res.json({ deleted: result.affectedRows });
  } catch (err) {
    res.status(500).json({ error: "Failed to delete graph" });
  }
};
