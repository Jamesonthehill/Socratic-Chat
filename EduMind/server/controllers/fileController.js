const db = require("../db");
const path = require("path");
const fs = require("fs-extra");
const { v4: uuidv4 } = require("uuid");
const axios = require("axios");
const FormData = require("form-data");

// Base path mounts to Docker volume 'file_storage'
const baseStoragePath = "/app/files";

exports.getFilesByUserAndProject = async (req, res) => {
  const { user_id, project_id } = req.params;

  try {
    const [rows] = await db.execute(
      `SELECT id,
      filename,
      file_type,
      text_extracted_flag,
      extracted_text_path as file_path,
      error_message, file_scan_flag,
      file_scan_message, uploaded_at,
      CASE 
      WHEN text_extracted_flag = 0 AND file_scan_flag = 0 THEN 'Extracting Text'
      WHEN text_extracted_flag = 1 AND file_scan_flag = 0 AND file_scan_message IS NULL THEN 'Waiting for Scan'
      WHEN text_extracted_flag = 1 AND file_scan_flag = 0 AND file_scan_message IS NOT NULL THEN 'Processing'
      WHEN text_extracted_flag = 1 AND file_scan_flag = 1 THEN 'Processing Complete'
      ELSE 'Pending'
      END AS status
      FROM files f
      WHERE f.user_id = ? AND f.project_id = ?
      ORDER BY f.uploaded_at DESC;
      `,
      [user_id, project_id]
    );

    res.json({ files: rows });
  } catch (err) {
    console.error("Error fetching files by user and project:", err.message);
    res.status(500).json({ error: "Failed to fetch files" });
  }
};

// Upload & extract text
exports.uploadFile = async (req, res) => {
  const { user_id, project_id } = req.body;
  const file = req.file;

  if (!file || !user_id) {
    return res.status(400).json({ error: "Missing file, user_id" });
  }

  // Validate user and team access
  const [[user]] = await db.execute("SELECT * FROM users WHERE id = ?", [
    user_id,
  ]);
  if (!user) return res.status(404).json({ error: "User not found" });

  // Save original files
  const file_id = uuidv4();
  const safeFilename = file.originalname.replace(/\s+/g, "_");
  const extension = path
    .extname(file.originalname)
    .toLowerCase()
    .slice(1)
    .toUpperCase();

  const uploadDir = path.join(baseStoragePath, "uploads");
  const filePath = path.join(uploadDir, `${file_id}_${safeFilename}`);

  await fs.ensureDir(uploadDir);

  await fs.writeFile(filePath, file.buffer);

  await db.execute(
    `INSERT INTO files (id, user_id, project_id, filename, file_type, size, file_path)
     VALUES (?, ?, ?, ?, ?, ?, ?)`,
    [file_id, user_id, project_id, safeFilename, extension, file.size, filePath]
  );

  // Save extracted files
  const outputDir = path.join(baseStoragePath, "project", project_id, "input");
  const outputPath = path.join(outputDir, `${safeFilename}.txt`);

  await fs.ensureDir(outputDir);

  try {
    const formData = new FormData();
    console.log("Sending to ML:", {
      filePath,
      output_path: outputPath,
    });
    formData.append("file", fs.createReadStream(filePath));
    formData.append("output_path", outputPath);

    const mlResponse = await axios.post(
      "http://edumind_ml:8000/api/v1/process-text",
      formData,
      {
        headers: formData.getHeaders(),
        maxContentLength: Infinity,
        maxBodyLength: Infinity,
      }
    );

    // Write output chunks to outputPath
    const extractedContent = await fs.readFile(
      mlResponse.data.output_path,
      "utf-8"
    );

    await fs.writeFile(outputPath, extractedContent);

    await db.execute(
      `UPDATE files
       SET text_extracted_flag = 1, extracted_text_path = ?
       WHERE id = ?`,
      [outputPath, file_id]
    );

    res.status(201).json({
      id: file_id,
      filename: safeFilename,
      file_type: extension,
      size: file.size,
      uploaded_at: new Date().toISOString(),
      status: "Processing", // Matches the logic used in GET
      message: "File uploaded and processed successfully",
      keywords: mlResponse.data.top_keywords,
    });
  } catch (err) {
    console.error("ML service error:", err.message);

    await db.execute(`UPDATE files SET error_message = ? WHERE id = ?`, [
      err.message,
      file_id,
    ]);

    res.status(500).json({
      error: "Processing failed",
      details: err.message,
    });
  }
};

exports.deleteFileById = async (req, res) => {
  const { file_id } = req.params;

  try {
    // Get file record
    const [[file]] = await db.execute(`SELECT * FROM files WHERE id = ?`, [
      file_id,
    ]);

    if (!file) {
      return res.status(404).json({ error: "File not found" });
    }

    // Delete physical files
    try {
      await fs.remove(file.file_path);
      if (file.extracted_text_path) {
        await fs.remove(file.extracted_text_path);
      }
    } catch (err) {
      console.warn("File system deletion warning:", err.message);
    }

    // Delete DB record
    await db.execute(`DELETE FROM files WHERE id = ?`, [file_id]);

    res.json({ success: true, message: "File deleted successfully" });
  } catch (err) {
    console.error("Delete file error:", err);
    res.status(500).json({ error: "Internal server error" });
  }
};
