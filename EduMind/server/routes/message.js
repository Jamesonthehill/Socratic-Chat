const express = require("express");
const router = express.Router();
const controller = require("../controllers/messageController");

router.post("/", controller.sendMessage);
router.get("/session", controller.getMessagesBySession);
router.get("/rag/health", controller.getRagHealth);
router.get("/rag/documents", controller.getRagDocs);

module.exports = router;
