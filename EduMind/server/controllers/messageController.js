const db = require("../db");
const { v4: uuidv4 } = require("uuid");
const { createQuestions } = require("../services/questionService");
const chatService = require("../services/chatService");

require("dotenv").config();

exports.getRagHealth = async (req, res) => {
  try {
    const response = await chatService.getRagHealth();
    res.status(200).json({
      status: "ok",
      data: response.data,
    });
  } catch (error) {
    console.error("Error checking RAG health:", error.message);
    res.status(error.response?.status || 500).json({
      status: "error",
      message: error.message,
    });
  }
};

exports.getRagDocs = async (req, res) => {
  try {
    const response = await chatService.getRagDocs();
    res.status(200).json({
      status: "ok",
      data: response.data,
    });
  } catch (error) {
    console.error("Error checking RAG Docs:", error.message);
    res.status(error.response?.status || 500).json({
      status: "error",
      message: error.message,
    });
  }
};

// Get all messages by session_id
exports.getMessagesBySession = async (req, res) => {
  const { session_id } = req.query;

  try {
    const [rows] = await db.execute(
      "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY created_at ASC",
      [session_id]
    );

    res.status(200).json({
      success: true,
      messages: rows,
    });
  } catch (error) {
    console.error("Error fetching messages:", error);
    res.status(500).json({
      success: false,
      message: "Failed to fetch messages.",
      error: error.message,
    });
  }
};

exports.sendMessage = async (req, res) => {
  const { user_id, session_id, project_id, role, user_message } = req.body;

  const user_message_id = uuidv4();
  let search_result;
  let system_message;
  let system_output;

  try {
    const user_message_created_at = new Date();
    console.log("[DB] Inserting user message...");
    await db.execute(
      `INSERT INTO chat_messages (id, session_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)`,
      [user_message_id, session_id, role, user_message, user_message_created_at]
    );
    const { intent, reasoning } = await chatService.userIntentDetection(
      user_message,
      session_id
    );

    console.log("[INTENT DETECTION] Detected intent:", intent);
    console.log("[INTENT DETECTION] Reasoning:", reasoning);

    // Action based on UID results
    if (intent === "search_graph") {
      const { question_count, question, command, difficulty_level } =
        await chatService.queryInterpretation(user_message, session_id);
        const request_params = {
          query: question,
          mode: "global",
          top_k: 10,
          max_token_for_text_unit: 4000,
          max_token_for_global_context: 4000,
          max_token_for_local_context: 4000,
        };
      search_result = await chatService.query(request_params);
      system_message = search_result.response;
      
    } else if (intent === "generate_questions") {
      const { question_count, question, command, difficulty_level } =
        await chatService.queryInterpretation(user_message, session_id);
      const request_params = {
          query: question,
          mode: "mix",
          only_need_context: true,
          top_k: 10,
          max_token_for_text_unit: 4000,
          max_token_for_global_context: 4000,
          max_token_for_local_context: 4000,
        };
      search_result = await chatService.query(request_params);

      // stateful API call { search_result, command, difficulty_level, question_count } -> { system_message, system_output }
      const { message, questions } = await chatService.questionGeneration(
        session_id,
        project_id,
        search_result.response,
        command,
        difficulty_level,
        question_count
      );
      system_message = message;
      system_output = questions;
    } else {
      system_message = await chatService.basicChat(user_message, session_id);
    }

    // Process generated questions
    if (!system_output) {
      system_output = "";
    } else {
      try {
        await createQuestions(user_id, session_id, project_id, system_output);
      } catch (error) {
        console.error("[DB ERROR] Failed to store questions:", error);
      }
    }

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

    console.log("[DB] System message inserted with ID:", system_message_id);

    res.json({
      success: true,
      message: "Functionality Ran Successfully.",
      user_message_id: user_message_id,
      system_message_id: system_message_id,
      ai_message: system_message,
      ai_questions: system_output,
      user_created_at: user_message_created_at,
      system_created_at: system_message_created_at,
    });
  } catch (e) {
    console.log(`Error occurred in backend sendMessage function: ${e}`);
    res.status(500).json({
      success: false,
      message: "An error occurred while processing the request.",
      error: e.message || "Unknown error",
      stack: process.env.NODE_ENV === "development" ? e.stack : undefined,
    });
  }
};
