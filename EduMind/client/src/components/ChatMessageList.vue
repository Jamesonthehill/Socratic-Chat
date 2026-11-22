<template>
  <div class="overflow-y-auto overflow-x-hidden scroller w-[80%] px-1 py-1">
    <transition-group name="fade" tag="div" class="relative">
      <MessageItem
        v-for="msg in sortedMessages"
        :key="`${msg.created_at}-${msg.role}`"
        :message="msg"
        :isMine="msg.role === 'user'"
      />
    </transition-group>
  </div>
</template>

<script setup>
  import { defineProps, computed } from 'vue'
  import MessageItem from './ChatMessageItem.vue'

  const props = defineProps({
    messages: Array,
  })

  const sortedMessages = computed(() =>
    [...props.messages].sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
  )
</script>

<style scoped>
  .overflow-y-auto {
    overflow-y: auto;
  }
  .flex-1 {
    flex: 1;
  }

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

  .fade-enter-active,
  .fade-leave-active {
    transition: all 0.1s ease;
    transform-origin: top left;
  }
  .fade-enter-from,
  .fade-leave-to {
    opacity: 0;
    transform: scale(0.98);
  }
</style>
