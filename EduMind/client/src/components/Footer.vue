<template>
  <footer class="w-full bg-gray-900 text-gray-200 py-3 px-4 mt-auto">
    <div
      class="mx-auto flex flex-col md:flex-row items-center md:justify-between gap-4"
    >
      <div class="flex items-center gap-3">
        <h4 class="font-bold tracking-tight">EduMind</h4>
      </div>

      <div class="text-xs text-gray-400 text-center md:text-right">
        <nav class="gap-4">
          <a
            href="https://github.com/jaltareyr/AQG-Edumind"
            target="_blank"
            class="hover:text-white flex items-center gap-1"
            >GitHub</a
          >
        </nav>
        © {{ new Date().getFullYear() }} EduMind. All rights reserved.
      </div>
    </div>
  </footer>
</template>

<script setup></script>
