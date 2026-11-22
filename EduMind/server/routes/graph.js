const express = require("express");
const router = express.Router();
const controller = require("../controllers/graphController");

router.get("/", controller.getAllGraphs);
router.get("/:id", controller.getGraphById);
router.get("/user/:userId", controller.getGraphsByUserId);
router.get("/team/:teamId", controller.getGraphsByTeamId);
router.post("/", controller.createGraph);
router.put("/:id", controller.updateGraph);
router.delete("/:id", controller.deleteGraph);

module.exports = router;
