<template>
  <div class="flex flex-col space-y-3 w-full shadow-sm rounded-4xl">
    <!-- Chat input area -->
    <div
      class="flex items-center bg-gray-200 rounded-4xl gap-x-2 px-2 focus:outline-none focus:ring-2 focus:ring-green-800"
    >
      <textarea
        :value="modelValue"
        :disabled="disabled"
        @input="onInput"
        @keydown.enter="handleKeydown"
        placeholder="Ready when you are..."
        class="flex-1 px-4 py-3 min-h-20 max-h-64 resize-y text-black overflow-y-auto rounded-4xl focus:outline-none scroller"
      />
      <div class="relative group">
        <button
          @click="emit('send')"
          :disabled="disabled"
          class="ml-3 flex items-center justify-center h-10 w-10 rounded-full hover:bg-gray-300 transition-colors cursor-pointer"
        >
          <Sparkles class="w-5 h-5 text-gray-600" />
        </button>
        <div
          class="fixed z-50 px-3 py-1 text-sm text-white bg-gray-500 rounded shadow-md opacity-0 group-hover:opacity-100 transition pointer-events-none whitespace-nowrap"
        >
          Chat with EduMind
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { Sparkles } from "lucide-vue-next";

const props = defineProps({
  modelValue: String,
  disabled: Boolean,
});

const emit = defineEmits(["update:modelValue", "send"]);

function onInput(e) {
  emit("update:modelValue", e.target.value);
}

function handleKeydown(e) {
  if (e.shiftKey) return;
  e.preventDefault();
  emit("send");
}
</script>

<style scoped>
/* Custom scrollbar styling (for both modals) */
.scroller::-webkit-scrollbar {
  width: 8px;
}
.scroller::-webkit-scrollbar-track {
  background: transparent;
}
.scroller::-webkit-scrollbar-thumb {
  background-color: #9298a0;
  border-radius: 4px;
}
.scroller::-webkit-scrollbar-thumb:hover {
  background-color: #a9b8ce;
}
</style>
