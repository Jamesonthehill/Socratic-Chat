<template>
  <div :class="['flex my-2 px-4', isMine ? 'justify-end' : 'justify-start']">
    <template v-if="isMetaMessage">
      <div
        class="flex items-center gap-2 bg-blue-100 text-blue-800 font-medium py-2 rounded-xl shadow-sm"
      >
        <Server class="w-5 h-5" />
        <span>{{ props.message.content }}</span>
      </div>
    </template>

    <div
      v-else
      ref="messageContainer"
      class="message-bubble"
      :class="[
        'px-4 py-2 break-words whitespace-pre-wrap sm:max-w-[90%]',
        isMine
          ? 'bg-gray-300 rounded-2xl ml-auto'
          : 'text-gray-800 rounded-2xl flex-1',
      ]"
      :style="{ minHeight: '1rem' }"
      v-html="isThinkingMessage ? renderThinking : renderedContent"
    ></div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted } from "vue";
import { marked } from "marked";
import DOMPurify from "dompurify";
import Prism from "prismjs";
import { Server } from "lucide-vue-next";

import "prismjs/components/prism-python";
import "prismjs/components/prism-javascript";

const props = defineProps({
  message: Object,
  isMine: Boolean,
});

const messageContainer = ref(null);

const elapsedTime = ref(0);

onMounted(() => {
  if (isThinkingMessage.value) {
    const interval = setInterval(() => {
      elapsedTime.value = Date.now() - new Date(props.message.created_at);
    }, 500);
    watch(
      () => props.message.content,
      (val) => {
        if (val !== "typing") clearInterval(interval);
      },
    );
  }
});

const isThinkingMessage = computed(() => props.message?.content === "typing");
const isMetaMessage = computed(() => props.message?.role === "meta");
const renderThinking = computed(() => {
  return elapsedTime.value > 2000
    ? '<span class="thinking-text">Thinking...</span>'
    : '<span class="dot-loader"><span>.</span><span>.</span><span>.</span></span>';
});

marked.setOptions({
  highlight: (code, lang) => {
    const grammar = Prism.languages[lang] || Prism.languages.plaintext;
    return Prism.highlight(code, grammar, lang);
  },
  breaks: true,
});

const renderedContent = computed(() =>
  props.isMine
    ? props.message.content
    : DOMPurify.sanitize(marked.parse(props.message.content || "")),
);

const highlight = () => {
  if (!props.isMine && messageContainer.value) {
    const codeBlocks = messageContainer.value.querySelectorAll("pre code");
    codeBlocks.forEach((block) => Prism.highlightElement(block));
  }
};

onMounted(highlight);
watch(
  () => props.message.content,
  async () => {
    await nextTick();
    highlight();
  },
);
</script>

<style scoped>
.my-2 {
  margin-top: 0.5rem;
  margin-bottom: 0.5rem;
}

::v-deep(pre) {
  background-color: #1e1e1e;
  color: #ffffff;
  padding: 0.75rem 1rem;
  border-radius: 0.5rem;
  margin: 0.5rem 0;
  overflow-x: auto;
  font-size: 0.9rem;
  line-height: 1.5;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
}

::v-deep(code) {
  font-family: "Fira Code", monospace;
  font-size: 0.875rem;
}

::v-deep(p > code),
::v-deep(li > code),
::v-deep(span > code) {
  background-color: #babdc0;
  color: #111827;
  padding: 0.2em 0.4em;
  border-radius: 0.3rem;
  font-size: 0.9rem;
}

::v-deep(blockquote) {
  border-left: 4px solid #93c5fd;
  background-color: #f1f5f9;
  padding: 0.6rem 1rem;
  margin: 0.6rem 0;
  font-style: italic;
  color: #475569;
  border-radius: 0.375rem;
}

::v-deep(a) {
  color: #2563eb;
  text-decoration: underline;
  transition: color 0.2s ease;
}

::v-deep(a:hover) {
  color: #1d4ed8;
}

::v-deep(pre),
::v-deep(pre code),
::v-deep(pre code span),
::v-deep(pre code span.token),
::v-deep(code) {
  font-family: "Fira Code", monospace !important;
  font-size: 0.95em !important;
}

::v-deep(pre) {
  background-color: #1e1e1e;
  color: #ffffff;
  padding: 0.75rem 1rem;
  border-radius: 0.5rem;
  margin: 0.5rem 0;
  overflow-x: auto;
  line-height: 1.5;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
}

::v-deep(p > code),
::v-deep(li > code),
::v-deep(span > code) {
  background-color: #babdc0;
  color: #111827;
  padding: 0.2em 0.4em;
  border-radius: 0.3rem;
  font-size: 0.9rem;
  font-family: "Fira Code", monospace !important;
}

::v-deep(ul),
::v-deep(ol) {
  margin: 0;
}

::v-deep(li) {
  margin: 0;
  padding-left: 1.2rem;

  line-height: 1.6;
}

::v-deep(li > p) {
  margin: 0;
}
</style>

<style>
.dot-loader span {
  display: inline-block;
  animation: dots 1.2s infinite;
  font-size: 1.5rem;
  color: #6b7280;
}

.dot-loader span:nth-child(2) {
  animation-delay: 0.2s;
}
.dot-loader span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes dots {
  0% {
    opacity: 0.3;
    transform: translateY(0);
  }
  50% {
    opacity: 1;
    transform: translateY(-2px);
  }
  100% {
    opacity: 0.3;
    transform: translateY(0);
  }
}

.thinking-text {
  font-weight: 400;
  color: #4b5563;
  animation: pulse 1.4s ease-in-out infinite;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 0.4;
  }
  50% {
    opacity: 1;
  }
}

.message-bubble {
  min-height: 2rem;
  transition:
    opacity 0.3s ease,
    transform 0.3s ease;
}
</style>
