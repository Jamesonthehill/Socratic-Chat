// services/lightragService.js

const { exec } = require("child_process");
const util = require("util");
const execAsync = util.promisify(exec);

async function restartLightrag(projectId) {
  // 1) Stop & remove old container (ignore errors)
  try {
    await execAsync("docker kill ml-service");
  } catch {
    /* ignore if no container named "lightrag" was running */
  }
  try {
    await execAsync("docker rm ml-service");
  } catch {
    /* ignore if no container named "lightrag" existed */
  }

  // 2) Merge process.env + override
  const newEnv = { ...process.env, PROJECT_ID: projectId };
  newEnv.WORKING_DIR = `/app/files/project/${projectId}/rag_storage`;
  newEnv.INPUT_DIR = `/app/files/project/${projectId}/input`;
  newEnv.WEBUI_TITLE = `${projectId}`;

  // 3) Build "-e KEY='value'" flags for each ENV var
  const envFlags = Object.entries(newEnv)
    .map(([key, value]) => {
      // Escape any single quotes in the value
      const safeVal = value.replace(/'/g, "'\\''");
      return `-e ${key}='${safeVal}'`;
    })
    .join(" ");

  // 4) Run a new container from the local image "aqg-edumind-ml-service:latest"
  const cmd = `docker run -d \
    --name ml-service \
    --network ai-ed-tools_default \
    -p 9621:9621 \
    -v ai-ed-tools_file_storage:/app/files \
    ${envFlags} \
    ai-ed-tools-ml-service:latest`;

  try {
    const { stdout, stderr } = await execAsync(cmd);
    console.log("New lightrag started:", stdout.trim());
    if (stderr) console.warn("docker run warnings:", stderr.trim());
  } catch (err) {
    console.error("Failed to launch lightrag:", err.stderr || err);
    throw new Error("Could not start lightrag container");
  }
}

module.exports = restartLightrag;
