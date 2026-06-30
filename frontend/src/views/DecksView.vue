<script setup lang="ts">
import { onMounted, ref } from "vue"
import { useRouter } from "vue-router"

import { useDecksStore } from "@/stores/decks"

const store = useDecksStore()
const router = useRouter()
const newName = ref("")

onMounted(() => void store.fetchDecks())

async function create(): Promise<void> {
  const name = newName.value.trim()
  if (!name) return
  const view = await store.createDeck(name)
  newName.value = ""
  await router.push(`/decks/${view.id}`)
}
</script>

<template>
  <section class="mx-auto max-w-4xl p-4">
    <h1 class="mb-4 text-xl font-semibold">Decks</h1>
    <form class="mb-6 flex gap-2" @submit.prevent="create">
      <input
        v-model="newName"
        placeholder="New deck name…"
        class="flex-1 rounded border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800"
      />
      <button type="submit" class="rounded bg-brand-500 px-4 py-2 text-sm font-medium text-white">
        Create
      </button>
    </form>

    <ul class="grid grid-cols-1 gap-3 sm:grid-cols-2">
      <li
        v-for="deck in store.decks"
        :key="deck.id"
        class="rounded-lg border border-slate-200 p-4 dark:border-slate-700"
      >
        <RouterLink :to="`/decks/${deck.id}`" class="font-medium hover:text-brand-500">
          {{ deck.name }}
        </RouterLink>
        <p class="mt-1 text-xs text-slate-500">
          {{ deck.format }} · {{ deck.distinct_cards }} cards · {{ deck.owned_percent }}% owned
        </p>
        <button
          type="button"
          class="mt-2 text-xs text-red-600 hover:underline"
          @click="store.deleteDeck(deck.id)"
        >
          Delete
        </button>
      </li>
    </ul>
    <p v-if="!store.decks.length" class="text-sm text-slate-500">No decks yet — create one above.</p>
  </section>
</template>
