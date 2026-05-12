const messagesEl = document.querySelector("#messages");
const formEl = document.querySelector("#chatForm");
const inputEl = document.querySelector("#messageInput");
const sendButton = document.querySelector("#sendButton");
const scanButton = document.querySelector("#scanButton");
const newChatButton = document.querySelector("#newChatButton");
const scanStatus = document.querySelector("#scanStatus");
const fileInput = document.querySelector("#fileInput");
const threadList = document.querySelector("#threadList");

const CONVERSATION_KEY = "my_rag_chatbot_conversation_id";
let conversationId = localStorage.getItem(CONVERSATION_KEY) || createConversationId();
localStorage.setItem(CONVERSATION_KEY, conversationId);

const history = [];

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

function setBusy(isBusy) {
  sendButton.disabled = isBusy;
  inputEl.disabled = isBusy;
}

async function getJson(url) {
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(await response.text());
  }

  return response.json();
}

async function postJson(url, payload = {}) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
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
    body: formData,
  });

  if (!response.ok) {
    throw new Error(await response.text());
  }

  return response.json();
}

async function deleteJson(url) {
  const response = await fetch(url, { method: "DELETE" });

  if (!response.ok) {
    throw new Error(await response.text());
  }

  return response.json();
}


async function loadConversation() {
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
  conversationId = createConversationId();
  localStorage.setItem(CONVERSATION_KEY, conversationId);
  scanStatus.textContent = "New chat started.";
  clearMessages();
  showWelcome();
  await loadThreadList();
  inputEl.focus();
}

newChatButton.addEventListener("click", startNewChat);

inputEl.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    formEl.requestSubmit();
  }
});

formEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = inputEl.value.trim();
  if (!message) return;

  inputEl.value = "";
  appendMessage("user", message);
  history.push({ role: "user", content: message });
  setBusy(true);

  try {
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
    appendMessage("assistant", data.answer, data.sources || []);
    history.push({ role: "assistant", content: data.answer });
    await loadThreadList();
  } catch (error) {
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
  const files = Array.from(fileInput.files || []);
  if (!files.length) return;

  scanButton.disabled = true;
  scanStatus.textContent = "Uploading and indexing...";

  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));

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
});

await loadConversation();
await loadThreadList();

