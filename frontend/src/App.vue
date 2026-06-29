<script setup lang="ts">
import { RouterLink, RouterView, useRouter } from "vue-router"

import { useAuthStore } from "@/stores/auth"

const auth = useAuthStore()
const router = useRouter()

function logout(): void {
  auth.logout()
  router.push({ name: "login" })
}
</script>

<template>
  <div class="min-h-screen bg-slate-50 text-slate-900">
    <header class="border-b border-slate-200 bg-white">
      <nav class="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
        <RouterLink to="/" class="text-lg font-semibold">CabbyCards</RouterLink>
        <button
          v-if="auth.isAuthenticated"
          type="button"
          class="text-sm text-slate-600 hover:text-slate-900"
          @click="logout"
        >
          Log out
        </button>
      </nav>
    </header>
    <main class="mx-auto max-w-5xl px-4 py-6">
      <RouterView />
    </main>
  </div>
</template>
