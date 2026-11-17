<template>
  <div
    v-if="!store.collapsedNav"
    class="fixed inset-0 z-40"
    @click="toggleSidebar"
    aria-hidden="true"
  ></div>
  <FocusTrap
    :active="!store.collapsedNav"
    :escapeDeactivates="true"
    :clickOutsideDeactivates="true"
    focusTrapOptions="{ allowOutsideClick: false }"
  >
    <aside
      v-if="!store.collapsedNav"
      class="bg-green-900 text-white flex flex-col justify-between overflow-hidden"
      role="dialog"
      aria-modal="true"
    >
      <div class="space-y-1 flex-1">
        <!-- Collapse Button -->
        <button
          class="w-10 h-10 flex items-center justify-center focus:outline-none hover:bg-green-800 rounded-full ml-auto"
          @click="toggleSidebar"
        >
          <component
            :is="store.collapsedNav ? ChevronRight : X"
            class="w-5 h-5 text-gray-400"
          />
        </button>
        <div class="m-2">
          <button
            v-if="!store.collapsedNav"
            class="flex items-center w-full py-2 hover:bg-white hover:text-green-900 gap-2 p-4"
            :class="store.collapsedNav ? 'justify-center' : 'justify-start'"
            @click="goHome"
          >
            <House class="w-5 h-5" />
            <span
              class="ml-2 transition-opacity duration-200"
              :class="store.collapsedNav ? 'opacity-0' : 'opacity-100'"
            >
              Home
            </span>
          </button>
          <button
            v-if="!store.collapsedNav"
            class="flex items-center w-full py-2 hover:bg-white hover:text-green-900 gap-2 p-4"
            :class="store.collapsedNav ? 'justify-center' : 'justify-start'"
            @click="goToQuestionsBank"
          >
            <Layers2 class="w-5 h-5" />
            <span
              class="ml-2 transition-opacity duration-200"
              :class="store.collapsedNav ? 'opacity-0' : 'opacity-100'"
            >
              All Questions
            </span>
          </button>
          <button
            v-if="!store.collapsedNav"
            class="flex items-center w-full py-2 hover:bg-white hover:text-green-900 gap-2 p-4"
            :class="store.collapsedNav ? 'justify-center' : 'justify-start'"
            @click="openDialog"
          >
            <Plus class="w-5 h-5" />
            <span
              class="ml-2 transition-opacity duration-200"
              :class="store.collapsedNav ? 'opacity-0' : 'opacity-100'"
            >
              New Project
            </span>
          </button>
        </div>
        <div v-if="!store.collapsedNav" class="mt-6">
          <span
            class="text-gray-400 pl-6"
            :class="store.collapsedNav ? 'opacity-0' : 'opacity-100'"
          >
            My Projects
          </span>
          <div class="mt-3 max-h-130 overflow-y-auto scroller">
            <div>
              <div
                v-for="project in projects"
                :key="project.id"
                class="px-10 py-2 text-gray-200 hover:bg-green-800 rounded-full cursor-pointer transition-colors duration-300"
                @click="goToProject(project.id)"
              >
                <div class="truncate whitespace-nowrap">
                  <span class="truncate">{{ project.name }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </aside>
  </FocusTrap>

  <!-- Modal Dialog for "New Project" -->
  <div
    v-if="showDialog"
    class="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50"
  >
    <div class="bg-gray-100 rounded-2xl w-11/12 max-w-md p-6">
      <h2 class="text-lg font-semibold text-gray-800 mb-4">Project Name</h2>
      <input
        v-model="newProjectName"
        type="text"
        placeholder="E.g. FastAPI"
        class="w-full px-4 py-2 border border-gray-400 rounded-full focus:outline-none focus:ring-2 focus:ring-green-800"
      />
      <p v-if="errorMessage" class="text-sm text-red-600 mt-2">
        {{ errorMessage }}
      </p>

      <!-- Introduction Banner (place this at the top of your modal or above project list) -->
      <div
        class="bg-gray-200 mt-3 text-gray-600 p-4 rounded-2xl mb-4"
        role="alert"
      >
        <p class="font-semibold flex items-center gap-2">
          <Lightbulb class="w-5 h-5 text-yellow-600" />
          What’s a project?
        </p>
        <p class="mt-1 text-sm">
          Projects keep chats, files, and custom instructions in one place. Use
          them for ongoing work, or just to keep things tidy.
        </p>
      </div>

      <div class="mt-6 flex justify-end space-x-4">
        <button
          class="px-4 py-2 bg-gray-300 rounded-full hover:bg-gray-400 transition-colors"
          @click="closeDialog"
          :disabled="creating"
        >
          Cancel
        </button>
        <button
          class="px-4 py-2 bg-green-800 text-white rounded-full hover:bg-green-700 transition-colors flex items-center"
          @click="submitNewProject"
          :disabled="creating || !newProjectName.trim()"
        >
          <span v-if="!creating">Create</span>
          <svg
            v-else
            class="animate-spin h-5 w-5 text-white"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              class="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              stroke-width="4"
            ></circle>
            <path
              class="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
            ></path>
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from "vue";
import { useRouter, useRoute } from "vue-router";
import {
  House,
  X,
  ChevronRight,
  Plus,
  Lightbulb,
  Layers2,
} from "lucide-vue-next";
import { useUserStore } from "@/stores/user";
import { createNewProject } from "../../api/chat";
import { useChatStore } from "@/stores/chats";
import { useStore } from "@/stores/index";
import { getProjects } from "../../api/chat";
import { useToast } from "vue-toast-notification";
import { FocusTrap } from "focus-trap-vue";

const toast = useToast();
const userStore = useUserStore();
const chatStore = useChatStore();
const store = useStore();

const user_id = userStore.user_id;

const router = useRouter();
const route = useRoute();

const active = ref("Quizzes");

// Modal state
const showDialog = ref(false);
const newProjectName = ref("");
const errorMessage = ref("");
const creating = ref(false);

function showToast() {
  toast.info("Switching Project, please wait@.");
}

const goHome = () => {
  router.push("/");
};

// All projects fetched from backend
const projects = ref([]);

// Toggle sidebar collapse
const toggleSidebar = () => {
  store.toggleNav();
};

// Set the active nav label
const setActive = (item) => {
  active.value = item;
};

// Open/close the "New Project" dialog
const openDialog = () => {
  newProjectName.value = "";
  errorMessage.value = "";
  showDialog.value = true;
};
const closeDialog = () => {
  showDialog.value = false;
  newProjectName.value = "";
  errorMessage.value = "";
};

// Submit new project to backend
const submitNewProject = async () => {
  const name = newProjectName.value.trim();
  if (!name) {
    errorMessage.value = "Project name cannot be empty.";
    return;
  }

  creating.value = true;
  errorMessage.value = "";

  try {
    const user_id = userStore.user_id;
    const data = await createNewProject(name, user_id);
    const newProject = data.project;

    // Refresh the project list

    const data_projects = await getProjects(user_id);
    projects.value = data_projects.projects || [];

    // Close dialog
    showDialog.value = false;
    newProjectName.value = "";
    errorMessage.value = "";

    // Navigate to the newly newProject project's page
    chatStore.setProjectId(newProject.id);
    router.push(`/p/${newProject.id}`);
  } catch (err) {
    console.error("Error creating project:", err);
    errorMessage.value =
      err.response?.data?.message ||
      "Failed to create project. Please try again.";
  } finally {
    creating.value = false;
  }
};

// Navigate to a specific project
const goToProject = (id) => {
  showToast();
  chatStore.setNewChat();
  router.push(`/p/${id}`);
  store.toggleNav();
};

const goToQuestionsBank = () => {
  store.toggleNav();
  router.push("/questions");
};

async function fetchProjects() {
  const data_projects = await getProjects(user_id);
  projects.value = data_projects.projects || [];
}

// On mount, fetch the latest projects
onMounted(async () => {
  if (route.params.project_id == "DEFAULT") {
    openDialog();
  }
  await fetchProjects();
  if (projects.value.length === 0) {
    openDialog();
  }
});

watch(
  () => route.params.project_id,
  async (projectId) => {
    if (projectId == null || projectId === "DEFAULT") {
      openDialog;
    }
    await fetchProjects();
  },
  { immediate: true },
);
</script>
