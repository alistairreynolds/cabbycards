<script setup lang="ts">
import { onMounted } from "vue"
import { RouterLink, RouterView, useRouter } from "vue-router"

import { useAuthStore } from "@/stores/auth"
import { useThemeStore } from "@/stores/theme"

const auth = useAuthStore()
const theme = useThemeStore()
const router = useRouter()

onMounted(() => {
  // After a refresh we have the token but not the user — fetch them.
  if (auth.isAuthenticated && auth.user === null) {
    void auth.fetchMe()
  }
})

function logout(): void {
  auth.logout()
  router.push({ name: "login" })
}
</script>

<template>
  <div class="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-900 dark:text-slate-100">
    <header class="border-b border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-800">
      <nav class="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <RouterLink to="/" class="text-lg font-bold text-brand-500">CabbyCards</RouterLink>
        <div class="flex items-center gap-4 text-sm">
          <button
            type="button"
            class="rounded px-2 py-1 hover:bg-slate-100 dark:hover:bg-slate-700"
            :title="theme.isDark ? 'Switch to light' : 'Switch to dark'"
            @click="theme.toggle"
          >
            {{ theme.isDark ? "☀️" : "🌙" }}
          </button>
          <template v-if="auth.isAuthenticated">
            <span class="hidden text-slate-500 sm:inline">{{ auth.user?.email }}</span>
            <button type="button" class="hover:text-brand-500" @click="logout">Log out</button>
          </template>
          <template v-else>
            <RouterLink to="/login" class="hover:text-brand-500">Log in</RouterLink>
            <RouterLink to="/register" class="hover:text-brand-500">Sign up</RouterLink>
          </template>
        </div>
      </nav>
    </header>
    <main class="mx-auto max-w-6xl px-4 py-6">
      <RouterView />
    </main>
  </div>
</template>
