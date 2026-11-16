const axios = require("axios");
const db = require("../db");
const ml_service = process.env.ML_SERVICE_URL || "http://ml-service:9621";

exports.generateSummary = async (session_id) => {
  const { data } = await axios.post(`${ml_service}/chat/summarize-memory`, {
    session_id,
  });
  return data;
};

exports.generateSessionTitle = async (session_id) => {
  const response = await axios.post(`${ml_service}/chat/title`, {
    session_id,
  });
  return response.data;
};

