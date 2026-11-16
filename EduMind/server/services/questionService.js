// services/questionService.js
const { v4: uuidv4 } = require("uuid");
const db = require("../db");

exports.createQuestions = async (
  user_id,
  session_id,
  project_id,
  questions
) => {
  for (const q of questions) {
    const question_id = uuidv4();
    const insertQuery = `
      INSERT INTO edumind.questions (
        id, user_id, session_id, project_id,
        question_text, options, correct_answers,
        difficulty_level, tags, source
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `;
    const params = [
      question_id,
      user_id,
      session_id,
      project_id || null,
      q.question,
      JSON.stringify(q.options),
      JSON.stringify(q.correct_options),
      q.difficulty_level || null,
      JSON.stringify(q.tags || []),
      q.source || "",
    ];
    await db.execute(insertQuery, params);
  }
};

exports.getQuestionById = async (id) => {
  const [rows] = await db.execute(
    "SELECT * FROM edumind.questions WHERE id = ? AND isArchived = 0",
    [id]
  );
  return rows[0] || null;
};

exports.getQuestionsByUserId = async (userId) => {
  const [rows] = await db.execute(
    "SELECT q.*, p.name as project_name FROM edumind.questions q JOIN edumind.projects p ON p.id = q.project_id WHERE q.user_id = ?",
    [userId]
  );
  return rows;
};

exports.getQuestionsBySessionId = async (session_id) => {
  const [rows] = await db.execute(
    "SELECT * FROM edumind.questions WHERE session_id = ? ORDER BY updated_at DESC",
    [session_id]
  );
  return rows;
};

exports.getQuestionsByGraphId = async (project_id) => {
  const [rows] = await db.execute(
    "SELECT * FROM edumind.questions WHERE project_id = ?",
    [project_id]
  );
  return rows;
};

exports.updateQuestion = async (id, updates) => {
  const allowedFields = {
    question_text: "question_text",
    options: "options",
    correct_answers: "correct_answers",
    difficulty_level: "difficulty_level",
    tags: "tags",
    isApproved: "isApproved",
  };

  const setClauses = [];
  const values = [];

  for (const key in updates) {
    if (allowedFields[key]) {
      setClauses.push(`${allowedFields[key]} = ?`);
      let val = updates[key];
      if (["options", "correct_answers", "tags"].includes(key)) {
        val = JSON.stringify(val);
      }
      values.push(val);
    }
  }

  if (setClauses.length === 0) {
    throw new Error("No valid fields to update.");
  }

  setClauses.push("updated_at = CURRENT_TIMESTAMP");
  values.push(id);

  const updateQuery = `
    UPDATE edumind.questions 
    SET ${setClauses.join(", ")} 
    WHERE id = ? AND isArchived = 0
  `;
  await db.execute(updateQuery, values);
};

exports.archiveQuestion = async (id) => {
  await db.execute(
    "UPDATE edumind.questions SET isArchived = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
    [id]
  );
};

exports.approveQuestion = async (id) => {
  await db.execute(
    "UPDATE edumind.questions SET isApproved = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND isArchived = 0",
    [id]
  );
}

exports.undoApprovalQuestion = async (id) => {
  await db.execute(
    "UPDATE edumind.questions SET isApproved = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND isArchived = 0",
    [id]
  );
}