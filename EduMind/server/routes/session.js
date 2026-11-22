const express = require("express");
const router = express.Router();
const controller = require("../controllers/sessionController");

router.post("/", controller.createNew);
router.get("/", controller.getAllSessions);
router.get(
  "/user/:user_id/project/:project_id",
  controller.getSessionsByProjectId
);
router.get("/:id", controller.getSessionById);
router.put("/:id", controller.updateSession);
router.delete("/:id", controller.deleteSession);
router.post("/title", controller.generateSessionTopic);
router.post("/summarize", controller.summarizeMemory);

module.exports = router;
