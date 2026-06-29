<script setup lang="ts">
import { onMounted } from "vue"

import { useAuthStore } from "@/stores/auth"

const auth = useAuthStore()

onMounted(() => {
  // Load the current user if we have a token but haven't fetched them yet
  // (e.g. after a page refresh).
  if (auth.isAuthenticated && auth.user === null) {
    void auth.fetchMe()
  }
})
</script>

<template>
  <section>
    <h1 class="text-2xl font-bold">Your collection</h1>
    <p class="mt-2 text-slate-600">
      Signed in as {{ auth.user?.email ?? "…" }}.
    </p>
    <p class="mt-6 text-slate-500">
      Collection and deck building land in upcoming slices.
    </p>
  </section>
</template>
