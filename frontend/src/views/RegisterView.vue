<script setup lang="ts">
import { ref } from "vue"
import { useRouter } from "vue-router"

import { ApiError } from "@/lib/api"
import { useAuthStore } from "@/stores/auth"

const auth = useAuthStore()
const router = useRouter()

const email = ref("")
const password = ref("")
const displayName = ref("")
const error = ref<string | null>(null)
const busy = ref(false)

// Dev: the backend uses Cloudflare's always-pass test secret, so any token works.
// A real Turnstile widget is a later polish.
const DEV_TURNSTILE_TOKEN = "dev-turnstile-token"

async function submit(): Promise<void> {
  error.value = null
  busy.value = true
  try {
    await auth.register(email.value, password.value, DEV_TURNSTILE_TOKEN, displayName.value || null)
    await router.push({ name: "collection" })
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : "Something went wrong"
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section class="mx-auto max-w-sm">
    <h1 class="text-2xl font-bold">Create your account</h1>
    <form class="mt-4 flex flex-col gap-3" @submit.prevent="submit">
      <input
        v-model="email"
        type="email"
        required
        placeholder="Email"
        class="rounded border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-800"
      />
      <input
        v-model="displayName"
        type="text"
        placeholder="Display name (optional)"
        class="rounded border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-800"
      />
      <input
        v-model="password"
        type="password"
        required
        minlength="8"
        placeholder="Password (min 8 chars)"
        class="rounded border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-800"
      />
      <p v-if="error" class="text-sm text-red-600">{{ error }}</p>
      <button
        type="submit"
        :disabled="busy"
        class="rounded bg-brand-500 px-4 py-2 font-medium text-white hover:bg-brand-600 disabled:opacity-50"
      >
        {{ busy ? "Creating…" : "Sign up" }}
      </button>
      <RouterLink to="/login" class="text-center text-sm text-brand-600 hover:underline">
        Already have an account? Log in
      </RouterLink>
    </form>
  </section>
</template>
