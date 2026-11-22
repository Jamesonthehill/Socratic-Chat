<template>
  <div class="flex flex-1 flex-col items-center justify-center px-4 h-full min-h-0">
    <!-- Logo or Icon can go here if you have one -->
    <h1 class="text-4xl font-extrabold text-green-900 mb-3">Welcome to EduMind</h1>
    <h2 class="text-lg text-gray-700 font-medium mb-5 max-w-xl text-center">
      Your AI-powered assistant for smarter course management, content organization, and automatic
      question generation.<br />
      Upload files and let EduMind help you generate assessments and quizzes with ease.
    </h2>
    <div class="mb-8 max-w-lg text-center text-gray-600">
      <div class="justify-center p-4 rounded-lg">
        <span class="font-semibold text-green-800">EduMind</span> simplifies academic workflows for
        instructors.
        <ul class="mt-2 mb-2 bg-gray-200 p-3 rounded-lg">
          <li>Upload and organize course files and notes</li>
          <li>Automatically generate high-quality questions and quizzes</li>
          <li>Manage projects, sessions, and collaborative teams</li>
          <li>Export quizzes for easy student access</li>
        </ul>
        <span>Get started by creating your first project or uploading your course material.</span>
      </div>
    </div>
    <Button type="fill" text="Get Started" @click="goToProjects()" />
  </div>
</template>

<script setup>
  import Button from '@/components/Button.vue'
  import { useRouter } from 'vue-router'

  const router = useRouter()

  function goToProjects() {
    router.push('/p/DEFAULT#Chat')
  }
</script>
