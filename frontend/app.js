const authScreen = document.querySelector("#authScreen");
const appShell = document.querySelector("#appShell");
const loginForm = document.querySelector("#loginForm");
const registerForm = document.querySelector("#registerForm");
const showLoginButton = document.querySelector("#showLoginButton");
const showRegisterButton = document.querySelector("#showRegisterButton");
const authStatus = document.querySelector("#authStatus");
const logoutButton = document.querySelector("#logoutButton");
const userBadge = document.querySelector("#userBadge");
const messagesEl = document.querySelector("#messages");
const formEl = document.querySelector("#chatForm");
const inputEl = document.querySelector("#messageInput");
const sendButton = document.querySelector("#sendButton");
const scanButton = document.querySelector("#scanButton");
const newChatButton = document.querySelector("#newChatButton");
const scanStatus = document.querySelector("#scanStatus");
const fileInput = document.querySelector("#fileInput");
const attachmentTray = document.querySelector("#attachmentTray");
const chatPanel = document.querySelector("#chatPanel");
const dropOverlay = document.querySelector("#dropOverlay");
const threadList = document.querySelector("#threadList");

const CONVERSATION_KEY = "my_rag_chatbot_conversation_id";
const AUTH_USER_KEY = "my_rag_chatbot_user";
const AUTH_SESSION_MS = 60 * 60 * 1000;
let currentUser = readStoredUser();
let conversationId = localStorage.getItem(CONVERSATION_KEY) || createConversationId();
localStorage.setItem(CONVERSATION_KEY, conversationId);

const history = [];
const pendingFiles = [];


function readStoredUser() {
  try {
    const storedUser = JSON.parse(localStorage.getItem(AUTH_USER_KEY) || "null");
    if (!storedUser) return null;
    if (isSessionExpired(storedUser)) {
      localStorage.removeItem(AUTH_USER_KEY);
      localStorage.removeItem(CONVERSATION_KEY);
      return null;
    }
    return storedUser;
  } catch {
    return null;
  }
}

function isSessionExpired(user = currentUser) {
  return !user?.expires_at || Date.now() > user.expires_at;
}

function expireSession(message = "Session expired. Please login again.") {
  localStorage.removeItem(AUTH_USER_KEY);
  localStorage.removeItem(CONVERSATION_KEY);
  currentUser = null;
  conversationId = createConversationId();
  localStorage.setItem(CONVERSATION_KEY, conversationId);
  clearMessages();
  clearPendingFiles();
  showSignedOut();
  authStatus.textContent = message;
}

function requireActiveSession() {
  if (!currentUser) {
    showSignedOut();
    authStatus.textContent = "Please login first.";
    return false;
  }

  if (isSessionExpired()) {
    expireSession();
    return false;
  }

  return true;
}

function setAuthMode(mode) {
  const isLogin = mode === "login";
  loginForm.classList.toggle("is-hidden", !isLogin);
  registerForm.classList.toggle("is-hidden", isLogin);
  showLoginButton.classList.toggle("is-active", isLogin);
  showRegisterButton.classList.toggle("is-active", !isLogin);
  authStatus.textContent = "";
}

function showAuthenticatedApp() {
  authScreen.classList.add("is-hidden");
  appShell.classList.remove("is-hidden");
  userBadge.textContent = currentUser ? `Signed in as ${currentUser.username}` : "";
}

function showSignedOut() {
  appShell.classList.add("is-hidden");
  authScreen.classList.remove("is-hidden");
  authStatus.textContent = "";
  setAuthMode("login");
}

function saveUser(user) {
  currentUser = {
    ...user,
    expires_at: Date.now() + AUTH_SESSION_MS,
  };
  localStorage.setItem(AUTH_USER_KEY, JSON.stringify(currentUser));
  showAuthenticatedApp();
}

function authHeaders(headers = {}) {
  const nextHeaders = { ...headers };
  if (currentUser?.user_id) {
    nextHeaders["X-User-Id"] = currentUser.user_id;
  }
  return nextHeaders;
}

function createConversationId() {
  return crypto.randomUUID();
}

function clearMessages() {
  messagesEl.replaceChildren();
  history.length = 0;
}

function showWelcome() {
  appendMessage("assistant", "Attach documents, then ask me a question about them.");
}

function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function isImageFile(file) {
  return file.type.startsWith("image/");
}

function clearPendingFiles() {
  pendingFiles.forEach((item) => {
    if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
  });
  pendingFiles.length = 0;
  renderAttachmentTray();
}

function removePendingFile(id) {
  const index = pendingFiles.findIndex((item) => item.id === id);
  if (index === -1) return;
  const [removed] = pendingFiles.splice(index, 1);
  if (removed.previewUrl) URL.revokeObjectURL(removed.previewUrl);
  renderAttachmentTray();
}

function addPendingFiles(files) {
  Array.from(files || []).forEach((file) => {
    pendingFiles.push({
      id: crypto.randomUUID(),
      file,
      previewUrl: isImageFile(file) ? URL.createObjectURL(file) : "",
    });
  });
  renderAttachmentTray();
}

function renderAttachmentTray() {
  attachmentTray.replaceChildren();
  attachmentTray.classList.toggle("has-attachments", pendingFiles.length > 0);

  pendingFiles.forEach((item) => {
    const chip = document.createElement("div");
    chip.className = "attachment-chip";

    if (item.previewUrl) {
      const image = document.createElement("img");
      image.className = "attachment-thumb";
      image.src = item.previewUrl;
      image.alt = item.file.name;
      chip.appendChild(image);
    } else {
      const icon = document.createElement("div");
      icon.className = "attachment-icon";
      icon.textContent = item.file.name.split(".").pop()?.slice(0, 3).toUpperCase() || "FILE";
      chip.appendChild(icon);
    }

    const info = document.createElement("div");
    info.className = "attachment-info";

    const name = document.createElement("div");
    name.className = "attachment-name";
    name.textContent = item.file.name;

    const meta = document.createElement("div");
    meta.className = "attachment-meta";
    meta.textContent = formatFileSize(item.file.size);

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "attachment-remove";
    remove.setAttribute("aria-label", `Remove ${item.file.name}`);
    remove.textContent = "×";
    remove.addEventListener("click", () => removePendingFile(item.id));

    info.append(name, meta);
    chip.append(info, remove);
    attachmentTray.appendChild(chip);
  });
}

function formatThreadDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function renderThreadList(conversations = []) {
  threadList.replaceChildren();

  if (!conversations.length) {
    const empty = document.createElement("div");
    empty.className = "thread-empty";
    empty.textContent = "No saved chats yet.";
    threadList.appendChild(empty);
    return;
  }

  conversations.forEach((conversation) => {
    const row = document.createElement("div");
    row.className = "thread-row";
    if (conversation.conversation_id === conversationId) {
      row.classList.add("is-active");
    }

    const button = document.createElement("button");
    button.type = "button";
    button.className = "thread-item";

    const title = document.createElement("span");
    title.className = "thread-title";
    title.textContent = conversation.title || "New conversation";

    const meta = document.createElement("span");
    meta.className = "thread-meta";
    meta.textContent = `${conversation.message_count || 0} messages · ${formatThreadDate(conversation.updated_at)}`;

    const settings = document.createElement("button");
    settings.type = "button";
    settings.className = "thread-settings";
    settings.title = "Chat settings";
    settings.setAttribute("aria-label", "Chat settings");
    settings.textContent = "⋯";

    const menu = document.createElement("div");
    menu.className = "thread-menu";

    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "thread-delete";
    deleteButton.textContent = "Delete chat";

    button.append(title, meta);
    menu.appendChild(deleteButton);
    row.append(button, settings, menu);

    button.addEventListener("click", () => selectConversation(conversation.conversation_id));
    settings.addEventListener("click", (event) => {
      event.stopPropagation();
      row.classList.toggle("is-menu-open");
    });
    deleteButton.addEventListener("click", (event) => {
      event.stopPropagation();
      deleteConversation(conversation.conversation_id);
    });

    threadList.appendChild(row);
  });
}

async function loadThreadList() {
  try {
    const data = await getJson("/api/conversations");
    renderThreadList(data.conversations || []);
  } catch (error) {
    renderThreadList([]);
  }
}

async function selectConversation(nextConversationId) {
  conversationId = nextConversationId;
  localStorage.setItem(CONVERSATION_KEY, conversationId);
  scanStatus.textContent = "";
  await loadConversation();
  await loadThreadList();
  inputEl.focus();
}

async function deleteConversation(targetConversationId) {
  const ok = confirm("Delete this chat? This will remove it from PostgreSQL.");
  if (!ok) return;

  try {
    const result = await deleteJson(`/api/conversations/${targetConversationId}`);
    if (!result.deleted) {
      scanStatus.textContent = "Chat was not found in the database.";
      await loadThreadList();
      return;
    }

    if (targetConversationId === conversationId) {
      conversationId = createConversationId();
      localStorage.setItem(CONVERSATION_KEY, conversationId);
      clearMessages();
      showWelcome();
    }

    scanStatus.textContent = "Chat deleted from database.";
    await loadThreadList();
  } catch (error) {
    scanStatus.textContent = `Delete failed: ${error.message}`;
  }
}

function appendMessage(role, content, sources = []) {
  const item = document.createElement("article");
  item.className = `message ${role}`;
  item.textContent = content;

  if (sources.length) {
    const sourceBlock = document.createElement("div");
    sourceBlock.className = "sources";
    sourceBlock.textContent = `Sources: ${sources.map((source) => source.title).join(", ")}`;
    item.appendChild(sourceBlock);
  }

  messagesEl.appendChild(item);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}



function showThinkingIndicator() {
  const steps = [
    "Reading your question",
    "Searching uploaded documents",
    "Checking the strongest sources",
    "Writing an answer",
  ];
  let stepIndex = 0;

  const item = document.createElement("article");
  item.className = "message assistant thinking-message";
  item.setAttribute("aria-live", "polite");

  const status = document.createElement("span");
  status.className = "thinking-status";
  status.textContent = steps[stepIndex];

  const dots = document.createElement("span");
  dots.className = "thinking-dots";
  dots.setAttribute("aria-hidden", "true");
  dots.innerHTML = "<span></span><span></span><span></span>";

  item.append(status, dots);
  messagesEl.appendChild(item);
  messagesEl.scrollTop = messagesEl.scrollHeight;

  const timer = window.setInterval(() => {
    stepIndex = (stepIndex + 1) % steps.length;
    status.textContent = steps[stepIndex];
  }, 1400);

  return {
    remove() {
      window.clearInterval(timer);
      item.remove();
    },
  };
}

function setBusy(isBusy) {
  sendButton.disabled = isBusy;
  inputEl.disabled = isBusy;
}

async function getJson(url) {
  const response = await fetch(url, { headers: authHeaders() });

  if (!response.ok) {
    throw new Error(await response.text());
  }

  return response.json();
}

async function postJson(url, payload = {}) {
  const response = await fetch(url, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await response.text());
  }

  return response.json();
}

async function postForm(url, formData) {
  const response = await fetch(url, {
    method: "POST",
    headers: authHeaders(),
    body: formData,
  });

  if (!response.ok) {
    throw new Error(await response.text());
  }

  return response.json();
}

async function uploadPendingFiles() {
  if (!pendingFiles.length) return null;
  if (!requireActiveSession()) return null;

  scanButton.disabled = true;
  scanStatus.textContent = "Uploading and indexing...";

  const formData = new FormData();
  formData.append("conversation_id", conversationId);
  pendingFiles.forEach((item) => formData.append("files", item.file));

  try {
    const data = await postForm("/api/documents/upload", formData);
    const skipped = data.skipped_files?.length
      ? ` Skipped unsupported file(s): ${data.skipped_files.join(", ")}.`
      : "";
    scanStatus.textContent = `${data.message} Processed ${data.documents_scanned} file(s), stored ${data.files_stored || 0} in PostgreSQL, added ${data.chunks_added} chunk(s).${skipped}`;
    clearPendingFiles();
    return data;
  } finally {
    fileInput.value = "";
    scanButton.disabled = false;
  }
}

function supportedFiles(files) {
  return Array.from(files || []).filter((file) => /\.(txt|md|pdf)$/i.test(file.name));
}

async function uploadFiles(files) {
  if (!requireActiveSession()) return;
  const accepted = supportedFiles(files);
  if (!accepted.length) {
    scanStatus.textContent = "Use .txt, .md, or .pdf files.";
    return;
  }

  scanButton.disabled = true;
  scanStatus.textContent = "Uploading and indexing...";

  const formData = new FormData();
  formData.append("conversation_id", conversationId);
  accepted.forEach((file) => formData.append("files", file));

  try {
    const data = await postForm("/api/documents/upload", formData);
    const skipped = data.skipped_files?.length
      ? ` Skipped unsupported file(s): ${data.skipped_files.join(", ")}.`
      : "";
    scanStatus.textContent = `${data.message} Processed ${data.documents_scanned} file(s), stored ${data.files_stored || 0} in PostgreSQL, added ${data.chunks_added} chunk(s).${skipped}`;
  } catch (error) {
    scanStatus.textContent = `Upload failed: ${error.message}`;
  } finally {
    fileInput.value = "";
    scanButton.disabled = false;
  }
}

async function deleteJson(url) {
  const response = await fetch(url, { method: "DELETE", headers: authHeaders() });

  if (!response.ok) {
    throw new Error(await response.text());
  }

  return response.json();
}


async function loadConversation() {
  if (!requireActiveSession()) return;
  clearMessages();

  try {
    const data = await getJson(`/api/conversations/${conversationId}`);
    if (!data.messages?.length) {
      showWelcome();
      return;
    }

    data.messages.forEach((message) => {
      appendMessage(message.role, message.content);
      history.push({ role: message.role, content: message.content });
    });
  } catch (error) {
    showWelcome();
  }
}

async function startNewChat() {
  if (!requireActiveSession()) return;
  conversationId = createConversationId();
  localStorage.setItem(CONVERSATION_KEY, conversationId);
  scanStatus.textContent = "New chat started.";
  clearMessages();
  showWelcome();
  await loadThreadList();
  inputEl.focus();
}


showLoginButton.addEventListener("click", () => setAuthMode("login"));
showRegisterButton.addEventListener("click", () => setAuthMode("register"));

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  authStatus.textContent = "Signing in...";
  try {
    const data = await postJson("/api/auth/login", {
      identifier: document.querySelector("#loginIdentifier").value.trim(),
      password: document.querySelector("#loginPassword").value,
    });
    saveUser(data.user);
    await loadConversation();
    await loadThreadList();
    inputEl.focus();
  } catch (error) {
    authStatus.textContent = `Login failed: ${error.message}`;
  }
});

registerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  authStatus.textContent = "Creating account...";
  try {
    const data = await postJson("/api/auth/register", {
      username: document.querySelector("#registerUsername").value.trim(),
      email: document.querySelector("#registerEmail").value.trim(),
      password: document.querySelector("#registerPassword").value,
    });
    saveUser(data.user);
    await startNewChat();
  } catch (error) {
    authStatus.textContent = `Register failed: ${error.message}`;
  }
});

logoutButton.addEventListener("click", () => {
  expireSession("");
});

newChatButton.addEventListener("click", startNewChat);

inputEl.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    formEl.requestSubmit();
  }
});

formEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!requireActiveSession()) return;
  const message = inputEl.value.trim();
  if (!message && !pendingFiles.length) return;

  inputEl.value = "";
  if (message) {
    appendMessage("user", message);
    history.push({ role: "user", content: message });
  }
  setBusy(true);
  let thinkingIndicator = null;

  try {
    await uploadPendingFiles();

    if (!message) {
      appendMessage("assistant", "File attached to this chat. Ask me a question about it when you are ready.");
      return;
    }

    thinkingIndicator = showThinkingIndicator();
    const data = await postJson("/api/chat", {
      message,
      conversation_id: conversationId,
      history: history.slice(-8),
      top_k: 4,
    });
    if (data.conversation_id) {
      conversationId = data.conversation_id;
      localStorage.setItem(CONVERSATION_KEY, conversationId);
    }
    thinkingIndicator?.remove();
    thinkingIndicator = null;
    appendMessage("assistant", data.answer, data.sources || []);
    history.push({ role: "assistant", content: data.answer });
    await loadThreadList();
  } catch (error) {
    thinkingIndicator?.remove();
    thinkingIndicator = null;
    appendMessage("assistant", `Request failed: ${error.message}`);
  } finally {
    setBusy(false);
    inputEl.focus();
  }
});

scanButton.addEventListener("click", () => {
  fileInput.click();
});

fileInput.addEventListener("change", async () => {
  await uploadFiles(fileInput.files || []);
});

chatPanel.addEventListener("dragover", (event) => {
  event.preventDefault();
  chatPanel.classList.add("is-dragging");
});

chatPanel.addEventListener("dragleave", (event) => {
  if (!chatPanel.contains(event.relatedTarget)) {
    chatPanel.classList.remove("is-dragging");
  }
});

chatPanel.addEventListener("drop", async (event) => {
  event.preventDefault();
  chatPanel.classList.remove("is-dragging");
  addPendingFiles(event.dataTransfer?.files || []);
});

setInterval(() => {
  if (currentUser && isSessionExpired()) {
    expireSession();
  }
}, 30 * 1000);

if (currentUser) {
  showAuthenticatedApp();
  await loadConversation();
  await loadThreadList();
} else {
  showSignedOut();
}

