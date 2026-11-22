<template>
  <div
    class="fixed inset-0 z-50 flex items-center justify-center backdrop-blur-sm bg-black/30"
  >
    <div
      class="relative bg-white max-w-2xl w-full p-6 rounded-2xl shadow-lg border border-gray-300 overflow-y-auto max-h-[90vh] scroller flex flex-col gap-5 text-sm"
    >
      <!-- Close button -->
      <button
        @click="$emit('close')"
        class="absolute top-4 right-4 text-gray-500 hover:text-black transition"
      >
        <X class="w-6 h-6" />
      </button>

      <!-- Main content -->
      <div class="flex flex-col gap-4">
        <!-- Question -->
        <div>
          <label class="font-semibold text-gray-700 block mb-1">Question</label>
          <div v-html="renderMarkdown(question.question_text)" class="prose" />
        </div>
        <!-- Source -->
        <div class="flex gap-2 items-center">
          <label class="font-semibold text-gray-700 block mb-1">Source</label>
          <a
            v-if="question.source"
            :href="question.source"
            class="underline text-blue-600 hover:text-blue-800 text-sm ml-1"
            target="_blank"
            rel="noopener noreferrer"
          >
            {{ question.source }}
          </a>
          <span v-else class="text-gray-500 text-sm ml-1">N/A</span>
        </div>
        <!-- Options -->
        <div>
          <label class="font-semibold text-gray-700 block mb-1">Options</label>
          <ul class="list-disc pl-6 space-y-2 bg-gray-100 rounded-lg py-2 px-3">
            <li
              v-for="(opt, idx) in question.options"
              :key="idx"
              class="flex items-center"
            >
              <span class="font-semibold mr-2 text-gray-500"
                >[{{ idx + 1 }}]</span
              >
              <span
                :class="isCorrect(idx) ? 'text-green-700 font-semibold' : ''"
                >{{ opt }}</span
              >
            </li>
          </ul>
        </div>
        <!-- Difficulty -->
        <div class="flex gap-2">
          <label class="font-semibold text-gray-700 block mb-1"
            >Difficulty Level</label
          >
          <span
            class="inline-block border border-blue-600 text-blue-700 px-2 py-0.5 rounded-full text-xs"
          >
            {{ question.difficulty_level || "N/A" }}
          </span>
        </div>

        <!-- Tags -->
        <div class="flex gap-2">
          <label class="font-semibold text-gray-700 block mb-1">Tags</label>
          <div class="flex flex-wrap gap-2">
            <span
              v-for="(tag, i) in question.tags || []"
              :key="i"
              class="px-2 py-0.5 rounded-full border text-xs"
              :style="{
                borderColor: getTagColor(tag),
                color: getTagColor(tag),
              }"
            >
              {{ tag }}
            </span>
          </div>
        </div>

        <!-- Status -->
        <div class="flex gap-2">
          <label class="font-semibold text-gray-700 block mb-1">Status</label>
          <span
            :class="
              question.isApproved === 'Approved'
                ? 'text-green-700'
                : 'text-red-600'
            "
            class="font-medium"
          >
            {{ question.isApproved || "Pending" }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { marked } from "marked";
import DOMPurify from "dompurify";
import { X } from "lucide-vue-next";
import Prism from "prismjs";

import "prismjs/themes/prism-tomorrow.css";
import "prismjs/components/prism-python";
import "prismjs/components/prism-javascript";

const props = defineProps({
  question: {
    type: Object,
    required: true,
  },
});

const renderMarkdown = (text) => {
  const html = marked.parse(text || "");
  console.log(DOMPurify.sanitize(html));
  return DOMPurify.sanitize(html);
};

const isCorrect = (index) => {
  return props.question.correct_answers?.includes(index);
};

function getTagColor(tag) {
  const hash = Array.from(tag).reduce(
    (acc, char) => acc + char.charCodeAt(0),
    0,
  );
  const hue = hash % 360;
  return `hsl(${hue}, 65%, 45%)`;
}
</script>

<style scoped>
.scroller::-webkit-scrollbar {
  width: 8px;
}

.scroller::-webkit-scrollbar-thumb {
  background-color: #9298a0;
  border-radius: 4px;
}
.scroller::-webkit-scrollbar-thumb:hover {
  background-color: #a9b8ce;
}

/* Reuse same card/markdown style */
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

.prose pre,
.prose pre code,
.prose pre code span,
.prose pre code span.token,
.prose code {
  font-family: "Fira Code", monospace !important;
  font-size: 0.95em !important;
}

.prose pre {
  background-color: #1e1e1e;
  color: #ffffff;
  padding: 1rem;
  border-radius: 0.5rem;
  margin: 0.5rem 0;
  overflow-x: auto;
  line-height: 1.5;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
}

.prose p > code,
.prose li > code,
.prose span > code {
  background-color: #babdc0;
  color: #111827;
  padding: 0.2em 0.4em;
  border-radius: 0.3rem;
  font-size: 0.9rem;
  font-family: "Fira Code", monospace !important;
}
</style>
