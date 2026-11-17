const express = require("express");
const router = express.Router();
const controller = require("../controllers/userTeamController");

router.post("/", controller.createUserTeam);
router.get("/user/:user_id", controller.getTeamsByUserId);
router.get("/:user_id/:team_id", controller.getUserTeam);
router.delete("/:user_id/:team_id", controller.deleteUserTeam);

module.exports = router;
