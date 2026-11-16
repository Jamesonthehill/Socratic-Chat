const express = require("express");
const router = express.Router();
const controller = require("../controllers/projectController");

// HEALTH CHECK (fixed route first)
router.get("/rag/health", controller.checkHealth);

// CREATE
router.post("/create", controller.createNew);

// INIT RAG SERVER
router.post("/init/:id", controller.initRag);

// READ
router.get("/user/:user_id", controller.getByUser);
router.get("/:id", controller.getById);

// UPDATE
router.put("/:id", controller.updateById);

// DELETE
router.delete("/:id", controller.deleteById);

module.exports = router;
