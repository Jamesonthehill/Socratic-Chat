const express = require("express");
const router = express.Router();
const controller = require("../controllers/userController");

router.post("/", controller.createUser);
router.get("/", controller.getAllUsers);
router.get("/:id", controller.getUser);
router.put("/:id", controller.updateUser);
router.delete("/:id", controller.deleteUser);

module.exports = router;
