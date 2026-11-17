import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useStore = defineStore('state', () => {
    const collapsedNav = ref(true)
    const columns = ref(2)

    function toggleNav() {
        collapsedNav.value = !collapsedNav.value
    }
    function setColumns(newColumns) {
        columns.value = newColumns
    }

    return {
        collapsedNav,
        toggleNav,
        columns,
        setColumns,
    }
})