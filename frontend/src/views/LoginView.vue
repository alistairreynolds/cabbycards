<script setup lang="ts">
import { ref } from "vue"
import { useRouter } from "vue-router"

import { ApiError } from "@/lib/api"
import { useAuthStore } from "@/stores/auth"

const auth = useAuthStore()
const router = useRouter()

const email = ref("")
const password = ref("")
const error = ref<string | null>(null)
const busy = ref(false)

async function submit(): Promise<void> {
  error.value = null
  busy.value = true
  try {
    await auth.login(email.value, password.value)
    await router.push({ name: "home" })
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : "Something went wrong"
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section class="mx-auto max-w-sm">
    <h1 class="text-2xl font-bold">Log in</h1>
    <form class="mt-4 flex flex-col gap-3" @submit.prevent="submit">
      <input
        v-model="email"
        type="email"
        required
        placeholder="Email"
        class="rounded border border-slate-300 px-3 py-2"
      />
      <input
        v-model="password"
        type="password"
        required
        placeholder="Password"
        class="rounded border border-slate-300 px-3 py-2"
      />
      <p v-if="error" class="text-sm text-red-600">{{ error }}</p>
      <button
        type="submit"
        :disabled="busy"
        class="rounded bg-slate-900 px-4 py-2 text-white disabled:opacity-50"
      >
        {{ busy ? "Logging in…" : "Log in" }}
      </button>
    </form>
  </section>
</template>
