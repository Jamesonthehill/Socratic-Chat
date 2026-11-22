<template>
  <div class="flex flex-col w-full flex-1 min-h-0">
    <div class="flex-1 overflow-y-auto scroller">
      <transition-group
        name="card"
        tag="div"
        :class="['grid gap-3 min-h-0 mr-3', gridColumnsClass]"
        appear
      >
        <div
          v-for="(card, index) in cards"
          :key="card.id"
          :class="[
            'p-4 rounded-xl relative border shadow',
            tweakLoading.has(card.id)
              ? 'border-4 border-purple-500 animate-pulse-border bg-white'
              : selectedCards.has(card.id)
                ? 'border-2 border-green-800 bg-gray-300'
                : 'border-gray-300 bg-white',
            updatedIds.has(card.id) ? 'updated' : '',
          ]"
          :style="{ '--enter-delay': `${index * 50}ms` }"
        >
          <div class="flex justify-end mb-4 border-b pb-4 border-gray-300">
            <!-- Right: Archive + Approve -->
            <div class="flex items-center gap-4">
              <!-- Tweak Button -->
              <div class="relative group">
                <button
                  @click="(e) => toggleTweak(card.id, e)"
                  class="flex items-center justify-center text-purple-700 hover:text-white hover:bg-purple-400 rounded-full w-10 h-10 transition"
                  title="Approve"
                >
                  <WandSparkles class="w-5 h-5" />
                </button>
                <div
                  class="fixed z-50 px-3 py-1 text-white bg-gray-500 rounded shadow-md opacity-0 group-hover:opacity-100 transition pointer-events-none whitespace-nowrap"
                >
                  Quick Edit using AI
                </div>
              </div>
              <!-- Approve Button -->
              <div class="relative group">
                <button
                  @click="() => handleApprove(card.id)"
                  class="flex items-center justify-center text-green-700 hover:text-white hover:bg-green-400 rounded-full w-10 h-10 transition"
                  title="Approve"
                >
                  <Check class="w-5 h-5" />
                </button>
                <div
                  class="fixed z-50 px-3 py-1 text-white bg-gray-500 rounded shadow-md opacity-0 group-hover:opacity-100 transition pointer-events-none whitespace-nowrap"
                >
                  Approve
                </div>
              </div>

              <!-- Archive Button -->
              <div class="relative group">
                <button
                  @click="handleArchive(card.id)"
                  class="flex items-center justify-center text-red-600 hover:text-white hover:bg-red-400 rounded-full w-10 h-10 transition"
                  title="Archive"
                >
                  <Archive class="w-5 h-5" />
                </button>
                <div
                  class="fixed z-50 px-3 py-1 text-white bg-gray-500 rounded shadow-md opacity-0 group-hover:opacity-100 transition pointer-events-none whitespace-nowrap"
                >
                  Archive
                </div>
              </div>
            </div>
          </div>
          <div class="flex flex-col gap-4">
            <!-- Question Text -->
            <div class="font-semibold">
              <div
                class="px-1"
                v-html="renderMarkdown(card.question_text)"
                :ref="(el) => highlightAfterRender(el)"
              />
            </div>
            <!-- Question Source -->
            <div class="font-semibold">
              <span class="mr-1">Source:</span>
              <a
                :href="card.source"
                class="underline text-blue-600 hover:text-blue-800"
                target="_blank"
                rel="noopener noreferrer"
              >
                {{ card.source }}
              </a>
            </div>
            <!-- Options -->
            <ul class="list-disc p-2 space-y-2 bg-gray-100 rounded-lg">
              <ul
                v-for="(opt, index) in getOptions(card)"
                :key="index"
                class="relative group"
              >
                <span class="mr-1">[{{ index + 1 }}]</span>
                {{
                  opt
                }}
              </ul>
            </ul>
            <!-- Correct Answers -->
            <div class="flex flex-wrap gap-2">
              <span class="font-semibold">Correct Answer(s)</span>
              <span
                v-for="ansIdx in card.correct_answers"
                :key="ansIdx"
                class="text-xs px-2 py-0.5 rounded-full text-white bg-green-700"
              >
                {{ getOptions(card)[ansIdx] }}
              </span>
            </div>
            <!-- Difficulty -->
            <div>
              <span class="font-semibold">Difficulty Level</span>
              <span
                class="text-xs ml-2 inline-block border border-blue-600 text-blue-600 px-2 rounded-full"
              >
                {{ card.difficulty_level }}
              </span>
            </div>

            <!-- Tags -->
            <div class="flex flex-wrap gap-2">
              <span class="font-semibold">Tag(s)</span>
              <template v-for="tag in card.tags" :key="index">
                <span
                  class="text-xs px-2 py-0.5 rounded-full border"
                  :style="{
                    borderColor: getTagColor(tag),
                    color: getTagColor(tag),
                  }"
                >
                  {{ tag }}
                </span>
              </template>
            </div>
          </div>
        </div>
      </transition-group>
    </div>
    <!-- Floating Tweak Box -->
    <div
      v-if="tweakPopup.activeId"
      :style="{ top: tweakPopup.top + 'px', left: tweakPopup.left + 'px' }"
      class="fixed z-50 bg-white border border-gray-300 rounded-xl shadow-xl px-4 py-2 flex items-center gap-2"
    >
      <input
        v-model="tweakInput[tweakPopup.activeId]"
        placeholder="Suggest question tweaks"
        class="border border-gray-300 rounded-lg px-2 py-1 w-64"
      />
      <button
        class="bg-purple-700 text-white px-3 py-1 rounded-full hover:bg-purple-800"
        @click="sendTweak(tweakPopup.activeId, route.params.session_id)"
      >
        Tweak
      </button>
      <button
        class="text-gray-500 hover:text-black"
        @click="tweakPopup.activeId = null"
        title="Cancel"
      >
        ✕
      </button>
    </div>
  </div>
</template>

<script setup>
defineExpose({ selectAll });
import { useRoute } from "vue-router";
import { ref, watch, nextTick, reactive, computed } from "vue";
import { Archive, Check, WandSparkles } from "lucide-vue-next";
import { marked } from "marked";
import Prism from "prismjs";
import DOMPurify from "dompurify";

import "prismjs/themes/prism-tomorrow.css";
import "prismjs/components/prism-python";
import "prismjs/components/prism-javascript";

import {
  getQuestionById,
  approveQuestion,
  archiveQuestionById,
} from "../../api/questions";

const props = defineProps({
  assets: {
    type: Array,
    required: true,
  },
  tweakComplete: String,
  columns: Number,
});

const route = useRoute();
const cards = computed(() => props.assets);
console.log("Cards: ", cards.value);
const getOptions = (card) => card.options;
const cardToArchive = ref(null);

async function handleArchive(cardId) {
  cardToArchive.value = cards.value.find((c) => c.id === cardId);
  if (!cardToArchive.value) return;
  try {
    await archiveQuestionById(cardToArchive.value.id);
    // Remove card from UI
    const idx = cards.value.findIndex((c) => c.id === cardToArchive.value.id);
    if (idx !== -1) cards.value.splice(idx, 1);
  } catch (error) {
    console.error("Error archiving question:", error);
    // Optionally show toast/error
  }
}

const gridColumnsClass = computed(() => ({
  "grid-cols-1": props.columns === 1,
  "grid-cols-2": props.columns === 2,
  "grid-cols-3": props.columns === 3,
}));

function getTagColor(tag) {
  const hash = Array.from(tag).reduce(
    (acc, char) => acc + char.charCodeAt(0),
    0,
  );
  const hue = hash % 360;
  return `hsl(${hue}, 65%, 45%)`;
}

marked.setOptions({
  highlight: (code, lang) => {
    const grammar = Prism.languages[lang] || Prism.languages.plaintext;
    return Prism.highlight(code, grammar, lang);
  },
  breaks: true,
});

const renderMarkdown = (text) => {
  const rawHTML = marked.parse(text || "");
  console.log(DOMPurify.sanitize(rawHTML));
  return DOMPurify.sanitize(rawHTML);
};

const highlightAfterRender = async (el) => {
  if (!el) return;
  await nextTick();
  el.querySelectorAll("pre code").forEach((block) =>
    Prism.highlightElement(block),
  );
};

const tweakInput = ref({});
const tweakPopup = ref({
  activeId: null,
  top: 0,
  left: 0,
});
const tweakLoading = ref(new Set());
const lastTweakedCardId = ref(null);

const updatedIds = ref(new Set());

watch(
  () => props.tweakComplete,
  async (tweakedId) => {
    if (!tweakedId) return;
    try {
      const data = await getQuestionById(tweakedId);
      console.log("updated question: ", data);
      const updated = data.question;
      const i = cards.value.findIndex((c) => c.id === tweakedId);
      if (i === -1) return;

      const old = cards.value[i];
      const clone = reactive({ ...old });
      cards.value.splice(i, 1, clone);

      await animateCardTransition(clone, updated);
      cards.value.splice(i, 1, reactive({ ...updated }));

      updatedIds.value.add(tweakedId);
      setTimeout(() => updatedIds.value.delete(tweakedId), 1000);
    } catch (err) {
      console.error("fetch after tweak failed", err);
    } finally {
      tweakLoading.value.delete(tweakedId);
    }
  },
);

async function animateCardTransition(clone, newCard) {
  const animateField = async (field, target) => {
    if (Array.isArray(target)) {
      clone[field] = [];
      for (const item of target) {
        await new Promise((r) => setTimeout(r, 100));
        clone[field].push(item);
      }
    } else if (typeof target === "string") {
      clone[field] = "";
      for (let i = 0; i <= target.length; i++) {
        await new Promise((r) => setTimeout(r, 20));
        clone[field] = target.slice(0, i);
      }
    } else {
      clone[field] = target;
    }
  };

  for (const field of [
    "question_text",
    "options",
    "correct_answers",
    "difficulty_level",
    "tags",
  ]) {
    await animateField(field, newCard[field]);
  }
}

function toggleTweak(id, event) {
  if (tweakPopup.value.activeId === id) {
    tweakPopup.value.activeId = null;
    return;
  }

  const rect = event.currentTarget.getBoundingClientRect();
  const tweakWidth = 340;
  const tweakHeight = 70;

  const leftRaw = rect.left + window.scrollX + 40;
  const topRaw = rect.top + window.scrollY - tweakHeight - 10;
  const left = Math.min(
    leftRaw,
    window.scrollX + window.innerWidth - tweakWidth - 60,
  );
  const top = Math.max(topRaw, window.scrollY + 10);

  tweakPopup.value = {
    activeId: id,
    top,
    left,
  };
}

async function sendTweak(id, session_id) {
  const user_message = tweakInput.value[id]?.trim();
  if (!user_message) return;

  tweakLoading.value = new Set(tweakLoading.value).add(id);
  lastTweakedCardId.value = id;

  try {
    emit("tweak-request", {
      id,
      session_id,
      user_message,
    });
  } catch (error) {
    console.error("Tweak request sending failed with error:", error);
  } finally {
    tweakInput.value[id] = "";
    tweakPopup.value.activeId = null;
  }
}

const emit = defineEmits(["update:selected-questions", "tweak-request"]);

const selectedCards = ref(new Map());

function selectAll(mode) {
  if (mode === "all") {
    const all = cards.value.map((c) => ({
      id: c.id,
      preview: (c.question_text || "").split(" ").slice(0, 2).join(" "),
    }));
    emit("update:selected-questions", all);
  } else {
    emit("update:selected-questions", []);
  }
}

function handleApprove(cardId) {
  approveQuestion(cardId, route.params.session_id)
    .then(() => {
      const index = cards.value.findIndex((c) => c.id === cardId);
      if (index !== -1) {
        cards.value.splice(index, 1);
      }
    })
    .catch((err) => console.error("Approve failed:", err));
}
</script>

<style>
.card-enter-from {
  opacity: 0;
  transform: scale(0.95) translateY(20px);
}
.card-enter-active {
  transition: all 1s ease;
  transition-delay: var(--enter-delay, 30ms);
}
.card-enter-to {
  opacity: 1;
  transform: scale(1) translateY(0);
}

.card-leave-active {
  transition: all 0.2s ease;
  opacity: 0;
  transform: scale(0.9) translateY(10px);
}

.prose pre {
  background-color: #2d2d2d;
  color: #f8f8f2;
  padding: 1rem;
  border-radius: 0.5rem;
  overflow-x: auto;
  font-family: "Fira Code", "Courier New", monospace;
  font-size: 0.875rem;
}

.prose code {
  font-family: "Fira Code", "Courier New", monospace;
  font-size: 0.85rem;
}

.prose a,
.markdown-body a {
  color: #2563eb; /* Tailwind blue-600, looks nice */
  text-decoration: underline;
  transition: color 0.2s;
}

.prose a:hover,
.markdown-body a:hover {
  color: #1d4ed8; /* Tailwind blue-700 on hover */
  text-decoration: underline;
}

@keyframes pulse-border {
  0% {
    box-shadow: 0 0 0 0 rgba(128, 90, 213, 0.4); /* purple-500 */
  }
  50% {
    box-shadow: 0 0 0 4px rgba(128, 90, 213, 0.2);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(128, 90, 213, 0.4);
  }
}

.animate-pulse-border {
  animation: pulse-border 1.5s infinite;
  border-color: #805ad5;
}

.updated {
  animation: fadeUpdate 0.6s ease;
}
@keyframes fadeUpdate {
  0% {
    background-color: #f0f8ff;
  }
  100% {
    background-color: transparent;
  }
}
</style>
