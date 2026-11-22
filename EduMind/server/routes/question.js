const express = require("express");
const router = express.Router();
const controller = require("../controllers/questionController");

router.post("/", controller.createQuestions);
router.get("/:id", controller.getQuestionById);
router.get("/user/:userId", controller.getQuestionsByUserId);
router.get("/session/:session_id", controller.getQuestionsBySessionId);
router.get("/project/:project_id", controller.getQuestionsByProjectId);
router.put("/:id", controller.updateQuestion);
router.post("/tweak/:id", controller.startQuestionTweak);
router.post("/approve/:id", controller.approveQuestion);
router.post("/undoApproval/:id", controller.undoApprovalQuestion);
router.post("/archive/:id", controller.archiveQuestion);
router.post("/export", controller.exportQuestions);

module.exports = router;
