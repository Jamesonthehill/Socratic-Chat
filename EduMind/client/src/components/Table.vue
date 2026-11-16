<template>
  <div class="overflow-x-auto max-w-full mx-auto min-h-110 scroller">
    <!-- Global Search -->
    <div class="mb-4 flex flex-wrap items-center gap-3 w-full">
      <!-- Left: search and reset -->
      <div class="flex items-center gap-3 flex-1 min-w-0">
        <div class="relative w-full sm:w-[40%] min-w-0">
          <input
            v-model="globalSearch"
            type="text"
            placeholder="Search"
            class="w-full h-10 pl-10 pr-3 py-2 border border-gray-300 rounded-full"
          />
          <Search
            class="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-500 w-5 h-5"
          />
        </div>
        <button
          v-if="anyFilterActive"
          class="flex gap-2 items-center h-10 px-4 py-2 text-sm rounded-full transition bg-red-200 hover:bg-red-300"
          @click="resetFilters"
        >
          <RouteOff class="w-5 h-5" />
          Reset Filters
        </button>
      </div>

      <!-- Right: count summary -->
      <span class="text-xs font-light text-gray-600 ml-auto">
        Showing {{ filteredRows.length }} of {{ rows.length }} rows
      </span>
    </div>

    <table
      class="border-b border-t border-gray-300 w-full min-w-full rounded-2xl table-fixed"
    >
      <thead>
        <tr class="bg-gray-100 border border-gray-300">
          <th
            v-for="(col, index) in columns"
            :key="col.key"
            :style="{ width: getColumnWidth(col) }"
            class="p-2 text-left relative group"
          >
            <!-- Label + Sorting + Filter Toggle -->
            <div class="flex items-center w-full">
              <!-- Sortable Label -->
              <div
                class="flex items-center gap-1 cursor-pointer"
                @click="col.sortable && toggleSort(col.key)"
              >
                <span>{{ col.label }}</span>
                <ArrowUpNarrowWide
                  v-if="
                    col.sortable && sortKey === col.key && sortOrder === 'asc'
                  "
                  class="w-4 h-4"
                />
                <ArrowUpWideNarrow
                  v-if="
                    col.sortable && sortKey === col.key && sortOrder === 'desc'
                  "
                  class="w-4 h-4"
                />
              </div>

              <!-- Filter Button -->
              <div v-if="col.filterable" class="relative">
                <button
                  @click="toggleFilterDropdown(col.key)"
                  class="text-xs focus:outline-none"
                  :class="{
                    'font-bold text-blue-500': columnFilters[col.key],
                    'text-gray-300': !columnFilters[col.key],
                  }"
                >
                  <component
                    :is="filterDropdown[col.key] ? ChevronUp : ChevronDown"
                    class="w-4 h-4 text-gray-700"
                  />
                </button>

                <!-- Filter Dropdown -->
                <!-- Filter Dropdown -->
                <div
                  v-if="filterDropdown[col.key]"
                  class="absolute mt-1 left-0 bg-white text-gray-500 rounded-lg shadow text-sm max-w-800 max-h-80 overflow-y-auto border border-gray-300 scroller"
                >
                  <div
                    class="px-3 py-1 hover:bg-gray-100 cursor-pointer"
                    @click="setFilter(col.key, 'ALL')"
                  >
                    <input
                      type="checkbox"
                      class="mr-2"
                      :checked="!columnFilters[col.key]?.length"
                      readonly
                    />
                    All
                  </div>
                  <div
                    v-for="val in getUniqueValues(col.key)"
                    :key="val"
                    class="px-3 py-1 hover:bg-gray-100 cursor-pointer flex items-center"
                    @click.stop="toggleMultiFilter(col.key, val)"
                  >
                    <input
                      type="checkbox"
                      class="mr-2"
                      :checked="columnFilters[col.key]?.includes(val)"
                      @change.stop=""
                      tabindex="-1"
                      readonly
                    />
                    <span>{{ val }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Resizer -->
            <div
              v-if="
                !col.width ||
                typeof col.width !== 'string' ||
                !col.width.endsWith('%')
              "
              class="absolute right-0 top-0 h-full w-1 cursor-col-resize group-hover:bg-gray-400"
              @mousedown="startResizing(col.key, $event)"
            ></div>
          </th>
        </tr>
      </thead>

      <tbody class="space-y-2">
        <tr
          v-for="(row, rowIndex) in paginatedRows"
          :key="rowIndex"
          class="hover:bg-gray-100"
          :class="{ 'bg-gray-300': selectedRows.includes(row) }"
        >
          <td
            v-for="col in columns"
            :key="col.key"
            class="p-2 py-2"
            :style="{ width: getColumnWidth(col) }"
          >
            <template v-if="col.link && col.external">
              <template v-if="isValidHttpUrl(row[col.key])">
                <a
                  :href="row[col.key]"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="text-blue-600 hover:underline"
                >
                  {{ row[col.key] }}
                </a>
              </template>
              <template v-else>
                {{ row[col.key] }}
              </template>
            </template>

            <template v-else-if="col.link && col.route">
              <router-link
                :to="generateRoute(col.route, row)"
                class="text-blue-600 hover:underline"
              >
                {{ row[col.key] }}
              </router-link>
            </template>
            <template v-else-if="col.link">
              <span
                class="text-blue-600 hover:underline cursor-pointer"
                @click="$emit('row-click', row)"
              >
                {{ row[col.key] }}
              </span>
            </template>
            <template v-else-if="col.type === 'status'">
              <span
                class="px-2 py-0.5 text-xs rounded-full text-white"
                :style="{
                  backgroundColor: getTagColor(row[col.key] || 'Unknown'),
                }"
              >
                {{ row[col.key] || "Unknown" }}
              </span>
            </template>
            <template
              v-else-if="col.type === 'actions' && Array.isArray(col.actions)"
            >
              <span class="flex gap-6 justify-start">
                <template v-for="(action, aIdx) in col.actions" :key="aIdx">
                  <router-link
                    v-if="action.route"
                    :to="generateRoute(action.route, row)"
                    :title="action.label"
                    class="flex items-center"
                  >
                    <component
                      v-if="action.icon"
                      :is="iconMap[action.icon]"
                      :class="['w-5 h-5', action.color]"
                      aria-hidden="true"
                    />
                  </router-link>
                  <button
                    v-else
                    @click.stop="action.action(row)"
                    :title="action.label"
                    class="flex items-center"
                  >
                    <component
                      v-if="action.icon"
                      :is="iconMap[action.icon]"
                      :class="['w-5 h-5', action.color]"
                      aria-hidden="true"
                    />
                  </button>
                </template>
              </span>
            </template>
            <template v-else-if="Array.isArray(row[col.key])">
              <div class="flex flex-wrap gap-1">
                <span
                  v-for="(tag, idx) in row[col.key]"
                  :key="idx"
                  class="px-2 py-0.5 text-xs rounded-full border"
                  :style="{
                    color: getTagColor(tag),
                    borderColor: getTagColor(tag),
                  }"
                >
                  {{ tag }}
                </span>
              </div>
            </template>
            <template v-else>
              {{ row[col.key] }}
            </template>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- Pagination Controls -->
    <div class="flex items-center justify-between mt-4">
      <!-- Rows per page -->
      <div class="flex items-center gap-2">
        <label class="text-sm text-gray-600">Rows per page:</label>
        <select
          v-model="rowsPerPage"
          class="text-sm border border-gray-300 px-2 py-1 rounded-full"
        >
          <option v-for="n in [8, 16, 24, 32]" :key="n" :value="n">
            {{ n }}
          </option>
        </select>
      </div>

      <!-- Page navigation -->
      <div class="flex items-center gap-4 text-sm">
        <span> Page {{ currentPage }} of {{ totalPages }} </span>

        <button
          @click="prevPage"
          :disabled="currentPage === 1"
          class="flex items-center gap-1 px-3 py-1 rounded-full bg-gray-200 hover:bg-gray-300 disabled:opacity-50"
        >
          <ChevronLeft class="w-4 h-4" />
          <span>Back</span>
        </button>

        <button
          @click="nextPage"
          :disabled="currentPage === totalPages"
          class="flex items-center gap-1 px-3 py-1 rounded-full bg-gray-200 hover:bg-gray-300 disabled:opacity-50"
        >
          <span>Next</span>
          <ChevronRight class="w-4 h-4" />
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from "vue";
import {
  ChevronUp,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Search,
  ArrowUpNarrowWide,
  ArrowUpWideNarrow,
  Trash,
  Edit,
  RouteOff,
  Check,
} from "lucide-vue-next";
const iconMap = { Trash, Edit, Check };

const props = defineProps({
  columns: Array,
  rows: Array,
});

const globalSearch = ref("");
const columnFilters = ref({});
const selectedRows = ref([]);
const columnWidths = ref({});
const filterDropdown = ref({});
const currentPage = ref(1);
const rowsPerPage = ref(16);
const sortKey = ref(null);
const sortOrder = ref("asc");

const emit = defineEmits(["row-click", "update:filteredRows"]);

// Resize logic
let resizingCol = null;
let startX = 0;
let startWidth = 0;

// Init widths on mount
onMounted(() => {
  props.columns.forEach((col) => {
    columnWidths.value[col.key] = 150;
  });
});

// Initialize filters and dropdown state
onMounted(() => {
  const sampleRows = props.rows.slice(0, 20); // Use first 20 rows for performance

  props.columns.forEach((col) => {
    const key = col.key;

    // Estimate average value length for this column
    const values = sampleRows.map((r) => r[key]);
    const avgLength =
      values.reduce((acc, v) => acc + String(v ?? "").length, 0) /
      (values.length || 1);

    let baseWidth = 80;
    if (avgLength < 8) baseWidth = 100;
    else if (avgLength < 20) baseWidth = 150;
    else if (avgLength < 40) baseWidth = 200;
    else baseWidth = 300;

    // Allow optional override via preferredWidth
    columnWidths.value[key] = col.preferredWidth || baseWidth;

    // Initialize filters
    columnFilters.value[key] = [];
    filterDropdown.value[key] = false;
  });
});

function getColumnWidth(col) {
  if (typeof col.width === "string" && col.width.endsWith("%")) {
    // If width is a percentage string, use it as-is
    return col.width;
  }
  // Otherwise, use your calculated/resized px width
  const w = columnWidths.value[col.key];
  return w ? w + "px" : undefined;
}

const anyFilterActive = computed(() => {
  return Object.values(columnFilters.value).some(
    (arr) => arr && arr.length > 0,
  );
});

// Row Filtering Logic
const filteredRows = computed(() => {
  let tempRows = props.rows.filter((row) => {
    const searchMatch = globalSearch.value
      ? Object.values(row).some((val) =>
          String(val).toLowerCase().includes(globalSearch.value.toLowerCase()),
        )
      : true;

    const filtersMatch = Object.entries(columnFilters.value).every(
      ([key, selectedVals]) => {
        if (!selectedVals?.length) return true;

        const col = props.columns.find((c) => c.key === key);
        if (col?.type === "array") {
          return (
            Array.isArray(row[key]) &&
            selectedVals.some((val) => row[key].includes(val))
          );
        }

        return selectedVals.includes(row[key]);
      },
    );

    return searchMatch && filtersMatch;
  });

  if (sortKey.value) {
    tempRows = [...tempRows].sort((a, b) => {
      const aVal = a[sortKey.value];
      const bVal = b[sortKey.value];

      if (aVal === bVal) return 0;
      if (sortOrder.value === "asc") return aVal > bVal ? 1 : -1;
      return aVal < bVal ? 1 : -1;
    });
  }

  return tempRows;
});

const paginatedRows = computed(() => {
  const start = (currentPage.value - 1) * rowsPerPage.value;
  return filteredRows.value.slice(start, start + rowsPerPage.value);
});

watch([filteredRows, rowsPerPage], () => {
  currentPage.value = 1;
  emit("update:filteredRows", filteredRows.value);
});

function getUniqueValues(key) {
  const col = props.columns.find((c) => c.key === key);

  if (col?.type === "array") {
    return [...new Set(props.rows.flatMap((row) => row[key] || []))].sort();
  }

  return [...new Set(props.rows.map((row) => row[key]))].sort();
}

function startResizing(colKey, event) {
  resizingCol = colKey;
  startX = event.clientX;
  startWidth = columnWidths.value[colKey];

  document.addEventListener("mousemove", resizeColumn);
  document.addEventListener("mouseup", stopResizing);
}

function isValidHttpUrl(string) {
  try {
    const url = new URL(string);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch (_) {
    return false;
  }
}

function resizeColumn(e) {
  if (!resizingCol) return;
  const delta = e.clientX - startX;
  const newWidth = Math.max(50, startWidth + delta);
  columnWidths.value[resizingCol] = newWidth;
}

function stopResizing() {
  document.removeEventListener("mousemove", resizeColumn);
  document.removeEventListener("mouseup", stopResizing);
  resizingCol = null;
}

function toggleFilterDropdown(key) {
  filterDropdown.value[key] = !filterDropdown.value[key];
  // Close others
  for (const k in filterDropdown.value) {
    if (k !== key) filterDropdown.value[k] = false;
  }
}

function setFilter(key, val) {
  // "All" resets filter
  if (val === "ALL") {
    columnFilters.value[key] = [];
  } else {
    columnFilters.value[key] = [val];
  }
  filterDropdown.value[key] = false;
}

function toggleMultiFilter(key, val) {
  const arr = columnFilters.value[key] || [];
  const idx = arr.indexOf(val);
  if (idx > -1) {
    arr.splice(idx, 1);
  } else {
    arr.push(val);
  }
  columnFilters.value[key] = [...arr];
}

function resetFilters() {
  globalSearch.value = "";
  for (const key in columnFilters.value) {
    columnFilters.value[key] = [];
  }
}

const totalPages = computed(
  () => Math.ceil(filteredRows.value.length / rowsPerPage.value) || 1,
);

function nextPage() {
  if (currentPage.value < totalPages.value) {
    currentPage.value++;
  }
}

function prevPage() {
  if (currentPage.value > 1) {
    currentPage.value--;
  }
}

function generateRoute(routeTemplate, row) {
  return routeTemplate.replace(/:([a-zA-Z_]+)/g, (_, key) => row[key] ?? "");
}

function toggleSort(key) {
  if (sortKey.value === key) {
    sortOrder.value = sortOrder.value === "asc" ? "desc" : "asc";
  } else {
    sortKey.value = key;
    sortOrder.value = "asc";
  }
}

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
* {
  user-select: none;
}

button:focus {
  outline: none;
}

.scroller::-webkit-scrollbar {
  width: 4px;
  height: 8px;
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
