<template>
  <div id="app" class="h-screen flex flex-col">
    <div class="flex flex-1 min-h-0">
      <!-- Sidebar: full height -->
      <Navbar v-if="!$route.meta.hideNavbar" class="h-full" />

      <!-- Main section: vertical stack of TopNavbar and main content -->
      <div class="flex flex-col flex-1 min-h-0">
        <TopNavbar />
        <main class="flex-1 min-h-0">
          <router-view />
          <Toaster position="top-right" richColors />
        </main>
      </div>
    </div>
    <Footer />
  </div>
</template>

<script setup>
  import Navbar from '@/components/Navbar.vue'
  import { Toaster } from 'vue-sonner'
  import TopNavbar from '@/components/TopNavbar.vue'
  import Footer from '@/components/Footer.vue'
</script>
