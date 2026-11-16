// mlServiceApi.js
const axios = require("axios");
const db = require("../db");
const ml_service = process.env.ML_SERVICE_URL || "http://ml-service:9621";

exports.getRagHealth = async () => {
  return axios.get(`${ml_service}/health`);
};

exports.getRagDocs = async () => {
  return axios.get(`${ml_service}/documents`);
};

exports.basicChat = async (user_message, session_id) => {
  const { data } = await axios.post(`${ml_service}/chat`, {
    user_message,
    session_id,
  });
  return data.system_message;
};

exports.queryInterpretation = async (user_message, session_id) => {
  const response = await axios.post(`${ml_service}/chat/query-interpret`, {
    user_message,
    session_id,
  });
  return response.data;
};

exports.query = async (params, stream = false) => {
  const response = await axios.post(`${ml_service}/query`, params);
  return response.data;
};

exports.questionGeneration = async (
  session_id,
  project_id,
  search_result,
  command,
  difficulty_level,
  question_count
) => {
  const [rows] = await db.execute(
    "SELECT instructions FROM edumind.projects WHERE id = ?",
    [project_id]
  );
  const instructions = rows[0]?.instructions ?? "";

  const response = await axios.post(
    `${ml_service}/chat/create-questions`,
    {
      session_id: session_id,
      question_count: question_count,
      difficulty_level: difficulty_level,
      search_result: search_result,
      command: command,
      instructions: instructions,
    },
    {
      headers: {
        "Content-Type": "application/json",
      },
    }
  );
  return response.data;
};

exports.userIntentDetection = async (user_message, session_id) => {
  const { data } = await axios.post(`${ml_service}/chat/user-intent`, {
    user_message,
    session_id,
  });
  return data;
};

exports.generateSummary = async (session_id) => {
  const { data } = await axios.post(`${ml_service}/chat/summarize-memory`, {
    session_id,
  });
  return data;
};
