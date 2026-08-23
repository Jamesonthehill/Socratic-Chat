const authScreen = document.querySelector("#authScreen");
const appShell = document.querySelector("#appShell");
const loginForm = document.querySelector("#loginForm");
const registerForm = document.querySelector("#registerForm");
const showLoginButton = document.querySelector("#showLoginButton");
const showRegisterButton = document.querySelector("#showRegisterButton");
const authStatus = document.querySelector("#authStatus");
const authCopy = document.querySelector("#authCopy");
const emailAuthDivider = document.querySelector("#emailAuthDivider");
const authTabs = document.querySelector("#authTabs");
const sendEmailCodeButton = document.querySelector("#sendEmailCodeButton");
const verificationCodeField = document.querySelector("#verificationCodeField");
const registerVerificationCode = document.querySelector("#registerVerificationCode");
const googleSignInWrap = document.querySelector("#googleSignInWrap");
const googleSignInButton = document.querySelector("#googleSignInButton");
const githubConnectWrap = document.querySelector("#githubConnectWrap");
const githubConnectMessage = document.querySelector("#githubConnectMessage");
const connectGithubButton = document.querySelector("#connectGithubButton");
const logoutButton = document.querySelector("#logoutButton");
const userIdentity = document.querySelector("#userIdentity");
const userInitial = document.querySelector("#userInitial");
const userName = document.querySelector("#userName");
const userBadge = document.querySelector("#userBadge");
const sessionWarning = document.querySelector("#sessionWarning");
const sessionWarningText = document.querySelector("#sessionWarningText");
const extendSessionButton = document.querySelector("#extendSessionButton");
const sessionLogoutButton = document.querySelector("#sessionLogoutButton");
const messagesEl = document.querySelector("#messages");
const formEl = document.querySelector("#chatForm");
const inputEl = document.querySelector("#messageInput");
const sendButton = document.querySelector("#sendButton");
const composerAttachButton = document.querySelector("#composerAttachButton");
const newChatButton = document.querySelector("#newChatButton");
const scanStatus = document.querySelector("#scanStatus");
const fileInput = document.querySelector("#fileInput");
const attachmentTray = document.querySelector("#attachmentTray");
const chatPanel = document.querySelector("#chatPanel");
const dropOverlay = document.querySelector("#dropOverlay");
const threadList = document.querySelector("#threadList");
const chatFilePanel = document.querySelector("#chatFilePanel");
const themeSelects = [...document.querySelectorAll(".theme-select")];
const themeColorMeta = document.querySelector('meta[name="theme-color"]');

const API_BASE_URL = (window.SOCRATIC_CONFIG?.API_BASE_URL || "").replace(/\/+$/, "");

function apiUrl(path) {
  if (/^https?:\/\//i.test(path)) return path;
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;
}

const CONVERSATION_KEY = "my_rag_chatbot_conversation_id";
const AUTH_USER_KEY = "my_rag_chatbot_user";
const THEME_KEY = "socratic_chat_theme";
const AUTH_SESSION_MS = 60 * 60 * 1000;
const SESSION_WARNING_MS = 5 * 60 * 1000;
const systemTheme = window.matchMedia("(prefers-color-scheme: dark)");
let renderGoogleSignInButton = null;
let currentUser = readStoredUser();
let conversationId = localStorage.getItem(CONVERSATION_KEY) || createConversationId();
localStorage.setItem(CONVERSATION_KEY, conversationId);
let emailVerificationRequired = true;
let authMode = "open";
let githubAccountRequired = false;
let githubOauthConfigured = false;

const history = [];
const pendingFiles = [];


function getThemePreference() {
  const storedTheme = localStorage.getItem(THEME_KEY);
  return ["light", "dark", "system"].includes(storedTheme) ? storedTheme : "light";
}

function applyTheme(preference, persist = true) {
  const safePreference = ["light", "dark", "system"].includes(preference) ? preference : "light";
  const resolvedTheme = safePreference === "system"
    ? (systemTheme.matches ? "dark" : "light")
    : safePreference;

  document.documentElement.dataset.theme = resolvedTheme;
  document.documentElement.dataset.themePreference = safePreference;
  themeSelects.forEach((select) => {
    select.value = safePreference;
  });
  if (themeColorMeta) {
    themeColorMeta.content = resolvedTheme === "dark" ? "#0d1117" : "#ffffff";
  }
  if (persist) localStorage.setItem(THEME_KEY, safePreference);
  renderGoogleSignInButton?.();
}

themeSelects.forEach((select) => {
  select.addEventListener("change", () => applyTheme(select.value));
});
systemTheme.addEventListener("change", () => {
  if (getThemePreference() === "system") applyTheme("system", false);
});
applyTheme(getThemePreference(), false);


function getDisplayName(user = currentUser) {
  const preferredName = user?.display_name || user?.username || user?.email?.split("@", 1)[0];
  return String(preferredName || "Student").trim();
}


function formatSessionTime(milliseconds) {
  const safeMilliseconds = Math.max(0, milliseconds);
  const totalSeconds = Math.ceil(safeMilliseconds / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes >= 60) {
    const hours = Math.floor(minutes / 60);
    const restMinutes = minutes % 60;
    return `${hours}h ${restMinutes}m`;
  }
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function persistCurrentUser() {
  if (currentUser) {
    localStorage.setItem(AUTH_USER_KEY, JSON.stringify(currentUser));
  }
}

async function extendSession() {
  if (!currentUser) return;
  const data = await postJson("/api/auth/session/refresh");
  currentUser.access_token = data.access_token;
  currentUser.expires_at = Date.now() + (data.expires_in_seconds * 1000);
  persistCurrentUser();
  updateSessionStatus();
}

function updateSessionStatus() {
  if (!sessionWarning) return;

  if (!currentUser) {
    if (userIdentity) userIdentity.classList.add("is-hidden");
    if (userName) userName.textContent = "";
    if (userInitial) userInitial.textContent = "";
    userBadge.textContent = "";
    sessionWarning.classList.remove("is-visible");
    sessionWarning.hidden = true;
    return;
  }

  const remaining = currentUser.expires_at - Date.now();
  const shouldWarn = remaining > 0 && remaining <= SESSION_WARNING_MS;
  const displayName = getDisplayName();
  if (userIdentity) userIdentity.classList.remove("is-hidden");
  if (userName) userName.textContent = displayName;
  if (userInitial) userInitial.textContent = displayName.charAt(0).toUpperCase();
  userBadge.textContent = `${currentUser.email || "Signed in"} · ${formatSessionTime(remaining)} left`;
  userBadge.classList.toggle("is-warning", shouldWarn);

  sessionWarning.hidden = !shouldWarn;
  sessionWarning.classList.toggle("is-visible", shouldWarn);
  if (sessionWarningText) {
    sessionWarningText.textContent = `${formatSessionTime(remaining)} left. Do you need more time?`;
  }
}

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
  if (authMode === "school_google" || authMode === "unavailable") {
    loginForm.classList.add("is-hidden");
    registerForm.classList.add("is-hidden");
    showLoginButton.classList.remove("is-active");
    showRegisterButton.classList.remove("is-active");
    return;
  }
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
  updateSessionStatus();
}

function showGithubConnection() {
  appShell.classList.add("is-hidden");
  authScreen.classList.remove("is-hidden");
  googleSignInWrap?.classList.add("is-hidden");
  githubConnectWrap?.classList.remove("is-hidden");
  if (authCopy) authCopy.textContent = "Step 2 of 2: connect the GitHub account you want linked to this school account.";
  if (githubConnectMessage) {
    githubConnectMessage.textContent = githubOauthConfigured
      ? `School account ${currentUser?.email || "verified"} is verified. Connect GitHub to continue.`
      : "GitHub authentication is not configured on the server yet.";
  }
  if (connectGithubButton) connectGithubButton.disabled = !githubOauthConfigured;
}

function enterAuthenticatedApp() {
  githubConnectWrap?.classList.add("is-hidden");
  if (githubAccountRequired && !currentUser?.github_connected) {
    showGithubConnection();
    return false;
  }
  showAuthenticatedApp();
  return true;
}

function showSignedOut() {
  appShell.classList.add("is-hidden");
  authScreen.classList.remove("is-hidden");
  authStatus.textContent = "";
  githubConnectWrap?.classList.add("is-hidden");
  googleSignInWrap?.classList.remove("is-hidden");
  updateSessionStatus();
  setAuthMode("login");
}

function saveUser(user, accessToken, expiresInSeconds = AUTH_SESSION_MS / 1000) {
  currentUser = {
    ...user,
    access_token: accessToken,
    expires_at: Date.now() + (expiresInSeconds * 1000),
  };
  localStorage.setItem(AUTH_USER_KEY, JSON.stringify(currentUser));
}

function authHeaders(headers = {}) {
  const nextHeaders = { ...headers };
  if (currentUser?.access_token) {
    nextHeaders.Authorization = `Bearer ${currentUser.access_token}`;
  } else if (currentUser?.user_id) {
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
  const greeting = currentUser ? `Hi ${getDisplayName()}, ` : "";
  appendMessage("assistant", `${greeting}attach documents, then ask me a question about them.`);
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




async function downloadChatFile(file) {
  if (!requireActiveSession()) return;

  const response = await fetch(apiUrl(`/api/documents/files/${encodeURIComponent(file.file_id)}/download`), {
    headers: authHeaders(),
  });

  if (!response.ok) {
    throw new Error(await responseErrorMessage(response));
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = file.filename || "download";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function renderChatFiles(files = []) {
  chatFilePanel.replaceChildren();

  const header = document.createElement("div");
  header.className = "chat-file-header";

  const title = document.createElement("span");
  title.textContent = "Files";

  const count = document.createElement("span");
  count.className = "chat-file-count";
  count.textContent = String(files.length);

  header.append(title, count);
  chatFilePanel.appendChild(header);

  if (!files.length) {
    const empty = document.createElement("div");
    empty.className = "chat-file-empty";
    empty.textContent = "No files in this chat";
    chatFilePanel.appendChild(empty);
    return;
  }

  const list = document.createElement("div");
  list.className = "chat-file-list";

  files.slice(0, 6).forEach((file) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "chat-file-item";
    item.title = `Download ${file.filename}`;
    item.setAttribute("aria-label", `Download ${file.filename}`);

    const icon = document.createElement("span");
    icon.className = "chat-file-icon";
    icon.textContent = (file.filename.split(".").pop() || "file").slice(0, 3).toUpperCase();

    const name = document.createElement("span");
    name.className = "chat-file-name";
    name.textContent = file.filename;

    item.append(icon, name);
    item.addEventListener("click", async () => {
      scanStatus.textContent = `Downloading ${file.filename}...`;
      try {
        await downloadChatFile(file);
        scanStatus.textContent = `Downloaded ${file.filename}.`;
      } catch (error) {
        scanStatus.textContent = `Download failed: ${error.message}`;
      }
    });
    list.appendChild(item);
  });

  chatFilePanel.appendChild(list);
}

async function loadChatFiles() {
  if (!currentUser || !conversationId) {
    renderChatFiles([]);
    return;
  }

  try {
    const data = await getJson(`/api/documents/files?conversation_id=${encodeURIComponent(conversationId)}`);
    renderChatFiles(data.files || []);
  } catch {
    renderChatFiles([]);
  }
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
  await loadChatFiles();
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

async function responseErrorMessage(response) {
  const rawMessage = (await response.text()).trim();
  if (!rawMessage) return `The request could not be completed (${response.status}).`;

  try {
    const payload = JSON.parse(rawMessage);
    if (typeof payload.detail === "string") return payload.detail;
    if (typeof payload.message === "string") return payload.message;
  } catch {
    if (rawMessage.startsWith("<")) {
      return "The server could not complete the request. Please try again.";
    }
  }

  return rawMessage;
}

async function getJson(url) {
  const response = await fetch(apiUrl(url), { headers: authHeaders() });

  if (!response.ok) {
    throw new Error(await responseErrorMessage(response));
  }

  return response.json();
}

async function postJson(url, payload = {}) {
  const response = await fetch(apiUrl(url), {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await responseErrorMessage(response));
  }

  return response.json();
}

async function postForm(url, formData) {
  const response = await fetch(apiUrl(url), {
    method: "POST",
    headers: authHeaders(),
    body: formData,
  });

  if (!response.ok) {
    throw new Error(await responseErrorMessage(response));
  }

  return response.json();
}

async function uploadPendingFiles() {
  if (!pendingFiles.length) return null;
  if (!requireActiveSession()) return null;

  composerAttachButton.disabled = true;
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
    await loadChatFiles();
    await loadThreadList();
    return data;
  } finally {
    fileInput.value = "";
    composerAttachButton.disabled = false;
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

  composerAttachButton.disabled = true;
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
    await loadChatFiles();
    await loadThreadList();
  } catch (error) {
    scanStatus.textContent = `Upload failed: ${error.message}`;
  } finally {
    fileInput.value = "";
    composerAttachButton.disabled = false;
  }
}

async function deleteJson(url) {
  const response = await fetch(apiUrl(url), { method: "DELETE", headers: authHeaders() });

  if (!response.ok) {
    throw new Error(await responseErrorMessage(response));
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
  clearPendingFiles();
  renderChatFiles([]);
  showWelcome();
  await loadChatFiles();
  await loadThreadList();
  inputEl.focus();
}


showLoginButton.addEventListener("click", () => setAuthMode("login"));
showRegisterButton.addEventListener("click", () => setAuthMode("register"));

async function finishAuth(data) {
  saveUser(data.user, data.access_token, data.expires_in_seconds);
  if (!enterAuthenticatedApp()) return;
  await loadConversation();
  await loadChatFiles();
  await loadThreadList();
  inputEl.focus();
}

async function connectGitHubAccount() {
  if (!currentUser?.access_token) {
    expireSession("Sign in with your school account first.");
    return;
  }
  connectGithubButton.disabled = true;
  authStatus.textContent = "Opening GitHub...";
  try {
    const data = await postJson("/api/auth/github/start");
    window.location.assign(data.authorize_url);
  } catch (error) {
    connectGithubButton.disabled = false;
    authStatus.textContent = `GitHub connection failed: ${error.message}`;
  }
}

connectGithubButton?.addEventListener("click", connectGitHubAccount);

async function handleGoogleCredential(response) {
  authStatus.textContent = "Signing in with Google...";
  try {
    const data = await postJson("/api/auth/google", { credential: response.credential });
    await finishAuth(data);
  } catch (error) {
    authStatus.textContent = error.message.includes("UNC Charlotte")
      ? error.message
      : `We couldn't complete Google sign-in. ${error.message}`;
  }
}

async function setupGoogleSignIn() {
  if (!googleSignInWrap || !googleSignInButton) return;

  try {
    const config = await getJson("/api/auth/google/config");
    if (!config.client_id) {
      googleSignInWrap.classList.add("is-hidden");
      return;
    }

    const initialize = () => {
      if (!window.google?.accounts?.id) {
        window.setTimeout(initialize, 200);
        return;
      }

      window.google.accounts.id.initialize({
        client_id: config.client_id,
        callback: handleGoogleCredential,
        hd: config.hosted_domain || undefined,
      });

      renderGoogleSignInButton = () => {
        googleSignInButton.replaceChildren();
        window.google.accounts.id.renderButton(googleSignInButton, {
          theme: document.documentElement.dataset.theme === "dark" ? "filled_black" : "outline",
          size: "large",
          width: 360,
          text: "continue_with",
          shape: "rectangular",
        });
      };
      renderGoogleSignInButton();
    };
    initialize();
  } catch {
    googleSignInWrap.classList.add("is-hidden");
  }
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  authStatus.textContent = "Signing in...";
  try {
    const data = await postJson("/api/auth/login", {
      identifier: document.querySelector("#loginIdentifier").value.trim(),
      password: document.querySelector("#loginPassword").value,
    });
    await finishAuth(data);
  } catch (error) {
    authStatus.textContent = `Login failed: ${error.message}`;
  }
});

function applyAuthenticationMode(config) {
  const required = Boolean(config.email_verification_required);
  authMode = config.auth_mode || "open";
  githubAccountRequired = Boolean(config.github_account_required);
  githubOauthConfigured = Boolean(config.github_oauth_configured);
  emailVerificationRequired = required;
  sendEmailCodeButton?.classList.toggle("is-hidden", !required);
  verificationCodeField?.classList.toggle("is-hidden", !required);
  if (registerVerificationCode) {
    registerVerificationCode.required = required;
    if (!required) registerVerificationCode.value = "";
  }

  const passwordAuthEnabled = config.password_auth_enabled !== false;
  if (!passwordAuthEnabled && currentUser && !currentUser.access_token) {
    expireSession("Please sign in again with your school Google account.");
  }
  emailAuthDivider?.classList.toggle("is-hidden", !passwordAuthEnabled);
  authTabs?.classList.toggle("is-hidden", !passwordAuthEnabled);
  loginForm?.classList.toggle("is-hidden", !passwordAuthEnabled);
  registerForm?.classList.add("is-hidden");

  if (!passwordAuthEnabled) {
    const domain = config.school_domain || "your school";
    if (authCopy) {
      authCopy.textContent = githubAccountRequired
        ? `Step 1 of 2: verify your ${domain} Google account, then connect GitHub.`
        : `Sign in with your ${domain} Google account to use the chatbot.`;
    }
  }
}

async function setupAuthenticationMode() {
  try {
    const config = await getJson("/api/auth/config");
    applyAuthenticationMode(config);
  } catch {
    applyAuthenticationMode({
      email_verification_required: false,
      auth_mode: "unavailable",
      password_auth_enabled: false,
      school_domain: "charlotte.edu",
      github_account_required: false,
      github_oauth_configured: false,
    });
    authStatus.textContent = "Authentication server unavailable. Check the Render API address.";
  }
}

async function restoreLinkedAccount() {
  if (!currentUser?.access_token) return;
  try {
    const data = await getJson("/api/auth/me");
    currentUser = { ...currentUser, ...data.user };
    persistCurrentUser();
  } catch {
    expireSession("Your session ended. Please sign in again.");
  }
}

async function requestEmailVerificationCode() {
  const email = document.querySelector("#registerEmail").value.trim();
  if (!email) {
    authStatus.textContent = "Enter your email first.";
    return;
  }

  sendEmailCodeButton.disabled = true;
  authStatus.textContent = "Sending verification code...";
  try {
    const data = await postJson("/api/auth/send-verification-code", { email });
    authStatus.textContent = `${data.message} It expires in ${data.expires_in_minutes} minutes.`;
    registerVerificationCode?.focus();
  } catch (error) {
    authStatus.textContent = `Could not send code: ${error.message}`;
  } finally {
    sendEmailCodeButton.disabled = false;
  }
}

sendEmailCodeButton?.addEventListener("click", requestEmailVerificationCode);

registerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  authStatus.textContent = "Creating account...";
  try {
    const data = await postJson("/api/auth/register", {
      username: document.querySelector("#registerUsername").value.trim(),
      email: document.querySelector("#registerEmail").value.trim(),
      password: document.querySelector("#registerPassword").value,
      verification_code: emailVerificationRequired ? registerVerificationCode.value.trim() : null,
    });
    await finishAuth(data);
  } catch (error) {
    authStatus.textContent = `Register failed: ${error.message}`;
  }
});

logoutButton.addEventListener("click", () => {
  expireSession("");
});

extendSessionButton?.addEventListener("click", async () => {
  try {
    await extendSession();
    scanStatus.textContent = "Session extended.";
  } catch {
    expireSession("Your session ended. Please sign in again.");
  }
});

sessionLogoutButton?.addEventListener("click", () => {
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

composerAttachButton.addEventListener("click", () => {
  fileInput.click();
});

fileInput.addEventListener("change", () => {
  addPendingFiles(fileInput.files || []);
  fileInput.value = "";
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

chatPanel.addEventListener("drop", (event) => {
  event.preventDefault();
  chatPanel.classList.remove("is-dragging");
  addPendingFiles(event.dataTransfer?.files || []);
});

setInterval(() => {
  if (currentUser && isSessionExpired()) {
    expireSession();
    return;
  }
  updateSessionStatus();
}, 1000);

await setupAuthenticationMode();
await setupGoogleSignIn();

const githubResult = new URLSearchParams(window.location.search).get("github");
if (githubResult) {
  window.history.replaceState({}, "", window.location.pathname + window.location.hash);
  if (githubResult !== "connected") {
    authStatus.textContent = "GitHub connection was not completed. Please try again.";
  }
}

await restoreLinkedAccount();

if (currentUser) {
  if (enterAuthenticatedApp()) {
    await loadConversation();
    await loadChatFiles();
    await loadThreadList();
  }
} else {
  renderChatFiles([]);
  showSignedOut();
}
