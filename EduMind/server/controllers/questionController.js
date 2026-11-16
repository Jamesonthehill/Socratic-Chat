const service = require("../services/questionService");
const axios = require("axios");
const db = require("../db");
const { v4: uuidv4 } = require("uuid");

const ml_service = process.env.ML_SERVICE_SERVER;

exports.createQuestions = async (req, res) => {
  const { user_id, session_id, graph_id, questions } = req.body;
  try {
    await service.createQuestions(user_id, session_id, graph_id, questions);
    res.status(201).json({ success: true, message: "Questions created." });
  } catch (error) {
    console.error("Create Questions Error:", error);
    res.status(500).json({ success: false, error: error.message });
  }
};

exports.getQuestionById = async (req, res) => {
  try {
    const question = await service.getQuestionById(req.params.id);
    res.json({ success: true, question });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
};

exports.getQuestionsByUserId = async (req, res) => {
  try {
    const questions = await service.getQuestionsByUserId(req.params.userId);
    res.json({ success: true, questions });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
};

exports.getQuestionsBySessionId = async (req, res) => {
  try {
    const questions = await service.getQuestionsBySessionId(
      req.params.session_id
    );
    res.json({ success: true, questions });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
};

exports.getQuestionsByProjectId = async (req, res) => {
  try {
    const questions = await service.getQuestionsByGraphId(
      req.params.project_id
    );
    res.json({ success: true, questions });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
};

exports.updateQuestion = async (req, res) => {
  try {
    await service.updateQuestion(req.params.id, req.body);
    res.json({ success: true, message: "Question updated." });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
};

exports.archiveQuestion = async (req, res) => {
  try {
    await service.archiveQuestion(req.params.id);
    res.json({ success: true, message: "Question archived." });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
};

exports.startQuestionTweak = async (req, res) => {
  const question_id = req.params.id;
  const { user_message, session_id } = req.body;

  if (!session_id || !question_id) {
    return res
      .status(400)
      .json({ success: false, error: "Missing sessionId or questionId" });
  }

  try {
    const question = await service.getQuestionById(question_id);

    if (!question) {
      return res
        .status(404)
        .json({ success: false, error: "Question not found" });
    }

    console.log("[DB] Inserting user message...");

    const user_message_id = uuidv4();
    const user_message_created_at = new Date();

    const questionText = question.question_text;
    const options = Array.isArray(question.options) ? question.options : [];
    const correctAnswers = Array.isArray(question.correct_answers)
      ? question.correct_answers.map(Number)
      : [];
    const difficulty = question.difficulty_level || "N/A";
    const tags = Array.isArray(question.tags) ? question.tags : [];

    const question_data = `Question Text: ${questionText}
    \n- Options: ${options.join(
      ", "
    )}\n- Correct Answers: ${correctAnswers.join(
      ", "
    )}\n- Difficulty: ${difficulty}\n- Tags: ${tags.join(
      ", "
    )}\nUser Feedback: ${user_message}`;

    await db.execute(
      `INSERT INTO chat_messages (id, session_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)`,
      [
        user_message_id,
        session_id,
        "user",
        user_message,
        user_message_created_at,
      ]
    );

    const fastapiResp = await axios.post(
      `${ml_service}/chat/tweak-single-question`,
      {
        session_id,
        user_message: user_message,
        question: question_data,
      }
    );

    const updated = fastapiResp.data;

    const system_message = updated.message;

    const system_output = {
      question_text: updated.question,
      options: updated.options,
      correct_answers: updated.correct_options,
      difficulty_level: updated.difficulty_level,
      tags: updated.tags || question.tags,
    };

    await service.updateQuestion(question_id, system_output);

    const system_message_id = uuidv4();
    const system_message_created_at = new Date();

    await db.execute(
      `INSERT INTO chat_messages (id, session_id, role, content, output, created_at) VALUES (?, ?, 'assistant', ?, ?, ?)`,
      [
        system_message_id,
        session_id,
        system_message,
        system_output,
        system_message_created_at,
      ]
    );

    console.log(
      "[FINAL STATUS] [TWEAK] System Message: \n{",
      system_message,
      "}"
    );
    console.log(
      "[FINAL STATUS] [TWEAK] System Output: \n{",
      system_output,
      "}"
    );

    return res.status(200).json({
      success: true,
      message: "Functionality Ran Successfully.",
      user_message_id: user_message_id,
      system_message_id: system_message_id,
      ai_message: system_message,
      ai_questions: system_output,
      user_created_at: user_message_created_at,
      system_created_at: system_message_created_at,
    });
  } catch (err) {
    console.error("Question tweak error:", err.message);
    return res.status(500).json({
      success: false,
      error: "Failed to tweak question",
    });
  }
};


exports.approveQuestion = async (req, res) => {
  const question_id = req.params.id;
  const { session_id } = req.body;

  if (!session_id || !question_id) {
    return res
      .status(400)
      .json({ success: false, error: "Missing sessionId or questionId" });
  }

  try {
    const question = await service.getQuestionById(question_id);

    if (!question) {
      return res
        .status(404)
        .json({ success: false, error: "Question not found" });
    }

    await service.approveQuestion(question_id);

    return res.status(200).json({
      success: true,
      message: "Question approved successfully.",
    });
  } catch (err) {
    console.error("Approve question error:", err.message);
    return res.status(500).json({
      success: false,
      error: "Failed to approve question",
    });
  }
};

exports.undoApprovalQuestion = async (req, res) => {
  const question_id = req.params.id;

  if (!question_id) {
    return res
      .status(400)
      .json({ success: false, error: "Missing questionId" });
  }

  try {
    await service.undoApprovalQuestion(question_id);

    return res.status(200).json({
      success: true,
      message: "Approval reverted successfully.",
    });
  } catch (err) {
    console.error("Undo approval error:", err.message);
    return res.status(500).json({
      success: false,
      error: "Failed to revert approval",
    });
  }
};

exports.exportQuestions = async (req, res) => {
  const { filename, fileformat, questions } = req.body
  try {

    payload = {
      filename: filename,
      fileformat: fileformat,
      questions: questions.map((q) => ({
        question: q.question_text,
        options: q.options,
        correct_options: q.correct_answers,
      })),
    };

    const response = await axios.post(`${ml_service}/chat/questions/export`, payload);
    const data = response.data;

    return res.status(200).json({
      success: true,
      export: data,
      message: "Question Exported successfully.",
    });
    } catch (err) {
      console.error("Export question error:", err.message);
      return res.status(500).json({
        success: false,
        error: "Failed to Export questions",
      });
    }
}