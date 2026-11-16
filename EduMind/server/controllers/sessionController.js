const db = require("../db");
const { v4: uuidv4 } = require("uuid");
const axios = require("axios");
const { generateSummary, generateSessionTitle } = require("../services/sessionService")

// Create a new session
exports.createNew = async (req, res) => {
  const { user_id, project_id } = req.body;
  const session_id = uuidv4();
  try {
    await db.execute(
      "INSERT INTO chat_sessions (id, topic, user_id, project_id) VALUES (?, 'Untitled', ?, ?)",
      [session_id, user_id, project_id]
    );
    res.status(200).json({
      success: true,
      message: "New Chat Session is created successfully.",
      session_id: session_id, // returning id also!
    });
  } catch (error) {
    console.error("Error creating new session:", error);
    res.status(500).json({
      success: false,
      message: "Failed to create new chat session.",
      error: error.message,
    });
  }
};

// Get all sessions
exports.getAllSessions = async (req, res) => {
  try {
    const [rows] = await db.execute(
      "SELECT * FROM chat_sessions ORDER BY created_at DESC"
    );
    res.status(200).json({
      success: true,
      sessions: rows,
    });
  } catch (error) {
    console.error("Error fetching sessions:", error);
    res.status(500).json({
      success: false,
      message: "Failed to fetch sessions.",
      error: error.message,
    });
  }
};

// Get session by ID
exports.getSessionById = async (req, res) => {
  const { id } = req.params;
  try {
    const [rows] = await db.execute(
      "SELECT * FROM chat_sessions WHERE id = ?",
      [id]
    );
    if (rows.length === 0) {
      return res.status(404).json({
        success: false,
        message: "Session not found.",
      });
    }
    res.status(200).json({
      success: true,
      session: rows[0],
    });
  } catch (error) {
    console.error("Error fetching session by ID:", error);
    res.status(500).json({
      success: false,
      message: "Failed to fetch session.",
      error: error.message,
    });
  }
};

// Get all sessions by user_id
exports.getSessionsByUserId = async (req, res) => {
  const { user_id } = req.params;
  try {
    const [rows] = await db.execute(
      "SELECT * FROM chat_sessions WHERE user_id = ? ORDER BY created_at DESC LIMIT 30",
      [user_id]
    );
    res.status(200).json({
      success: true,
      sessions: rows,
    });
  } catch (error) {
    console.error("Error fetching sessions by user_id:", error);
    res.status(500).json({
      success: false,
      message: "Failed to fetch sessions by user_id.",
      error: error.message,
    });
  }
};

// Get all sessions by user_id
exports.getSessionsByProjectId = async (req, res) => {
  const { user_id, project_id } = req.params;
  try {
    const [rows] = await db.execute(
      "SELECT * FROM chat_sessions WHERE user_id = ? AND project_id = ? ORDER BY created_at DESC LIMIT 30",
      [user_id, project_id]
    );
    res.status(200).json({
      success: true,
      sessions: rows,
    });
  } catch (error) {
    console.error("Error fetching sessions by user_id and project_id:", error);
    res.status(500).json({
      success: false,
      message: "Failed to fetch sessions by user_id and project_id.",
      error: error.message,
    });
  }
};

// Update session (only topic can be updated realistically)
exports.updateSession = async (req, res) => {
  const { id } = req.params;
  const { topic } = req.body;
  try {
    const [result] = await db.execute(
      "UPDATE chat_sessions SET topic = ? WHERE id = ?",
      [topic, id]
    );
    if (result.affectedRows === 0) {
      return res.status(404).json({
        success: false,
        message: "Session not found.",
      });
    }
    res.status(200).json({
      success: true,
      message: "Session updated successfully.",
    });
  } catch (error) {
    console.error("Error updating session:", error);
    res.status(500).json({
      success: false,
      message: "Failed to update session.",
      error: error.message,
    });
  }
};

// Delete session
exports.deleteSession = async (req, res) => {
  const { id } = req.params;
  try {
    const [result] = await db.execute(
      "DELETE FROM chat_sessions WHERE id = ?",
      [id]
    );
    if (result.affectedRows === 0) {
      return res.status(404).json({
        success: false,
        message: "Session not found.",
      });
    }
    res.status(200).json({
      success: true,
      message: "Session deleted successfully.",
    });
  } catch (error) {
    console.error("Error deleting session:", error);
    res.status(500).json({
      success: false,
      message: "Failed to delete session.",
      error: error.message,
    });
  }
};

exports.generateSessionTopic = async (req, res) => {
  const { session_id } = req.body;
  if (!session_id) {
    return res
      .status(400)
      .json({ success: false, message: "Missing session_id." });
  }

  try {
    const data = await generateSessionTitle(session_id)
    const topic = data.title.trim();
    await db.execute("UPDATE chat_sessions SET topic = ? WHERE id = ?", [
      topic,
      session_id,
    ]);

    res.status(200).json({ success: true, topic, session_id });
  } catch (error) {
    console.error("Error generating topic:", error);
    res.status(500).json({
      success: false,
      message: "Failed to generate topic.",
      error: error.message,
    });
  }
};

exports.summarizeMemory = async (req, res) => {
  const { session_id } = req.body;

  if (!session_id) {
    return res
      .status(400)
      .json({ success: false, message: "Missing session_id." });
  }

  try {
    const data = await generateSummary(session_id)

    res.status(200).json({
      success: true,
      message: data.message,
      updated: data.updated,
      session_id,
    });
  } catch (error) {
    console.error("Error summarizing memory:", error.response?.data || error);
    res.status(500).json({
      success: false,
      message: "Failed to summarize memory.",
      error: error.message,
    });
  }
};
