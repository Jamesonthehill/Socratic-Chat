<template>
  <div
    v-if="auth.isAuthenticated"
    class="relative flex p-1 items-center shadow-sm border-gray-200 gap-2 bg-gray-200"
  >
    <!-- Left section -->
    <button
      v-if="showHeader"
      class="flex items-center justify-center w-10 h-10 hover:bg-gray-300 rounded-full"
      @click="store.toggleNav"
    >
      <Menu class="w-5 h-5" />
    </button>
    <div class="flex gap-2 items-center" v-if="showHeader">
      <div
        class="text-base font-bold text-green-800 cursor-pointer transition-all duration-300"
        @click="goHome"
      >
        EduMind
      </div>
      <div>|</div>
      <div
        class="font-semibold hover:text-green-500 cursor-pointer transition-all duration-300"
        @click="goToProject"
      >
        {{ projectName }}
      </div>
    </div>
    <!-- Nav buttons centered absolutely -->
    <div
      v-if="route.params.project_id"
      class="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 flex gap-2"
    >
      <button
        v-for="page in pages"
        :key="page"
        @click="navigate(page)"
        :class="[
          'm-1 p-2 w-20 text-center cursor-pointer transition-all duration-300',
          current === page
            ? 'underline decoration-2 underline-offset-6 text-black'
            : 'hover:bg-gray-300 text-gray-700',
        ]"
      >
        {{ page }}
      </button>
    </div>
    <!-- You can add any right-side content here if needed -->
    <div class="ml-auto flex items-center">
      <template v-if="auth.isAuthenticated">
        <button
          class="h-10 items-center flex gap-2 ml-2 px-3 py-1 hover:bg-red-400 cursor-pointer transition-all duration-300"
          @click="handleLogout"
        >
          <LogOut class="w-5 h-5" />
          Log Out
        </button>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { LogOut } from "lucide-vue-next";
import { getProject, createTitle } from "../../api/chat";
import { Menu } from "lucide-vue-next";
import { useStore } from "@/stores/index";
import { useAuthStore } from "@/stores/auth";

const route = useRoute();
const router = useRouter();
const store = useStore();
const auth = useAuthStore();

const projectName = ref("");
const pages = ["Files", "Chat", "Questions"];

watch(
  () => route.params.project_id,
  async (projectId) => {
    if (projectId == null || projectId === "DEFAULT") return;

    const data = await getProject(projectId);
    projectName.value = data.project.name;
  },
  { immediate: true },
);

const current = computed(() => {
  const hash = route.hash?.replace("#", "") || "Chat";
  return pages.includes(hash) ? hash : "Chat";
});

const showHeader = computed(() => {
  return !["Login", "Home"].includes(route.name);
});

function goHome() {
  createTitle(route.params.session_id);
  router.push({ name: "Home" });
}

function goToProject() {
  createTitle(route.params.session_id);
  router.push(`/p/${route.params.project_id}`);
}

const handleLogout = () => {
  createTitle(route.params.session_id);
  auth.logout();
  router.push({ name: "Login" });
};

const navigate = (page) => {
  const projectId = route.params.project_id;
  const sessionId = route.params.session_id;

  switch (page) {
    case "Files":
      router.push(`/p/${projectId}#Files`);
      break;
    case "Questions":
      router.push(`/p/${projectId}#Questions`);
      break;
    case "Chat":
      if (sessionId) {
        router.push(`/chat/${sessionId}/p/${projectId}#Chat`);
      } else {
        router.push(`/p/${projectId}`);
      }
      break;
  }
};
</script>
