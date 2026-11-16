const { v4: uuidv4 } = require("uuid");
const db = require("../db");
const restartLightrag = require("../services/restartLightrag");
const { default: axios } = require("axios");

require("dotenv").config();
const rag_service = process.env.RAG_SERVICE_SERVER;

// ---------------------------------------------
// POST /create
// ---------------------------------------------
exports.createNew = async (req, res) => {
  const { name, user_id } = req.body;
  if (!name || !user_id) {
    return res.status(400).json({
      success: false,
      error: "Missing required fields: name and user_id are required.",
    });
  }

  // Generate a new UUID for the project
  const id = uuidv4();

  // Prepare the SQL to insert into edumind.projects
  const insertSql = `
    INSERT INTO edumind.projects (id, name, user_id)
    VALUES (?, ?, ?)
  `;

  try {
    // 1) INSERT project into the database
    await db.execute(insertSql, [id, name, user_id]);

    // 2) Attempt to restart LightRAG with this new project ID
    try {
      await restartLightrag(id);
    } catch (containerError) {
      console.error("Error restarting lightrag container:", containerError);
      // If the container fails to start, return a 500
      return res.status(500).json({
        success: false,
        error: "Project created, but failed to start the lightrag container.",
        details: containerError.message,
      });
    }

    // 3) If we reach here, both DB insert and container start succeeded
    return res.status(201).json({
      success: true,
      project: {
        id,
        name,
        user_id,
        created_at: new Date().toISOString(),
      },
      message: `New project created and lightrag container started (PROJECT_ID=${id}).`,
    });
  } catch (error) {
    console.error("Create Project Error:", error);
    return res
      .status(500)
      .json({ success: false, error: "Failed to create project." });
  }
};

// ---------------------------------------------
// GET /:id
// ---------------------------------------------
exports.getById = async (req, res) => {
  const { id } = req.params;

  try {
    const [rows] = await db.execute(
      "SELECT * FROM edumind.projects WHERE id = ?",
      [id]
    );

    if (rows.length === 0) {
      return res
        .status(404)
        .json({ success: false, error: "Project not found." });
    }

    return res.status(200).json({ success: true, project: rows[0] });
  } catch (error) {
    console.error("Fetch Project by ID Error:", error);
    return res
      .status(500)
      .json({ success: false, error: "Failed to fetch project." });
  }
};

// ---------------------------------------------
// GET /user/:user_id
// ---------------------------------------------
exports.getByUser = async (req, res) => {
  const { user_id } = req.params;

  try {
    const [rows] = await db.execute(
      "SELECT * FROM edumind.projects WHERE user_id = ? ORDER BY created_at DESC",
      [user_id]
    );
    return res.status(200).json({ success: true, projects: rows });
  } catch (error) {
    console.error("Fetch Projects by User ID Error:", error);
    return res
      .status(500)
      .json({ success: false, error: "Failed to fetch projects by user." });
  }
};

// ---------------------------------------------
// PUT /:id
// ---------------------------------------------
exports.updateById = async (req, res) => {
  const { id } = req.params;
  const { name, user_id, instructions } = req.body;

  console.log({ name, user_id, instructions });

  if (
    name === undefined &&
    user_id === undefined &&
    instructions === undefined
  ) {
    return res.status(400).json({
      success: false,
      error:
        "Nothing to update. Provide at least `name`, `user_id`, or `instructions`.",
    });
  }

  const fields = [];
  const values = [];

  if (name !== undefined) {
    fields.push("name = ?");
    values.push(name);
  }
  if (user_id !== undefined) {
    fields.push("user_id = ?");
    values.push(user_id);
  }
  if (instructions !== undefined) {
    fields.push("instructions = ?");
    values.push(instructions);
  }

  values.push(id);

  const sql = `UPDATE edumind.projects SET ${fields.join(", ")} WHERE id = ?`;

  try {
    const [result] = await db.execute(sql, values);

    if (result.affectedRows === 0) {
      return res
        .status(404)
        .json({ success: false, error: "Project not found." });
    }

    return res.status(200).json({
      success: true,
      message: "Project updated successfully.",
    });
  } catch (error) {
    console.error("Update Project Error:", error);
    return res.status(500).json({
      success: false,
      error: "Failed to update project.",
    });
  }
};

// ---------------------------------------------
// DELETE /:id
// ---------------------------------------------
exports.deleteById = async (req, res) => {
  const { id } = req.params;

  try {
    const [result] = await db.execute(
      "DELETE FROM edumind.projects WHERE id = ?",
      [id]
    );

    if (result.affectedRows === 0) {
      return res
        .status(404)
        .json({ success: false, error: "Project not found." });
    }

    return res
      .status(200)
      .json({ success: true, message: "Project deleted successfully." });
  } catch (error) {
    console.error("Delete Project by ID Error:", error);
    return res
      .status(500)
      .json({ success: false, error: "Failed to delete project." });
  }
};

exports.initRag = async (req, res) => {
  const { id } = req.params;

  // Optionally, you can verify the project exists first:
  try {
    const [rows] = await db.execute(
      "SELECT id FROM edumind.projects WHERE id = ?",
      [id]
    );

    if (rows.length === 0) {
      return res
        .status(404)
        .json({ success: false, error: "Project not found." });
    }
  } catch (err) {
    console.error("DB lookup error in initRag:", err);
    return res
      .status(500)
      .json({ success: false, error: "Failed to verify project." });
  }

  // Attempt to restart LightRAG for this project ID
  try {
    await restartLightrag(id);
    return res.status(200).json({
      success: true,
      message: `LightRAG container initialized (PROJECT_ID=${id}).`,
    });
  } catch (containerError) {
    console.error("Error initializing lightrag container:", containerError);
    return res.status(500).json({
      success: false,
      error: "Failed to start or restart the LightRAG container.",
      details: containerError.message,
    });
  }
};

exports.checkHealth = async (req, res) => {
  try {
    const response = await axios.get(`${rag_service}/health`);
    res.status(200).json({
      success: true,
      status: response.status,
      data: response.data,
    });
  } catch (error) {
    console.error("Health check failed:", error.message);
    res.status(500).json({
      success: false,
      error: "Failed to reach RAG service",
      details: error.response?.data || error.message,
    });
  }
};

exports.saveInstructions = async (req, res) => {
  const { id } = req.params;
  const { instructions } = req.body;

  if (!instructions) {
    return res.status(400).json({
      success: false,
      error: "Instructions are required.",
    });
  }

  try {
    // Update the project with the new instructions
    const [result] = await db.execute(
      "UPDATE edumind.projects SET instructions = ? WHERE id = ?",
      [instructions, id]
    );

    if (result.affectedRows === 0) {
      return res
        .status(404)
        .json({ success: false, error: "Project not found." });
    }

    return res.status(200).json({
      success: true,
      message: "Instructions saved successfully.",
    });
  } catch (error) {
    console.error("Save Instructions Error:", error);
    return res.status(500).json({
      success: false,
      error: "Failed to save instructions.",
    });
  }
}