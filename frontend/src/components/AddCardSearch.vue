<script setup lang="ts">
import { ref } from "vue"

import { apiFetch } from "@/lib/api"

interface SearchCard {
  scryfall_id: string
  name: string
  data: Record<string, unknown>
}

const emit = defineEmits<{ add: [card: SearchCard] }>()

const query = ref("")
const results = ref<SearchCard[]>([])
const busy = ref(false)
const error = ref<string | null>(null)

async function search(): Promise<void> {
  const term = query.value.trim()
  if (!term) {
    return
  }
  busy.value = true
  error.value = null
  try {
    results.value = await apiFetch<SearchCard[]>(`/cards/search?q=${encodeURIComponent(term)}`)
  } catch {
    error.value = "Search failed — try again."
    results.value = []
  } finally {
    busy.value = false
  }
}

function thumbnail(card: SearchCard): string | undefined {
  const data = card.data as {
    image_uris?: { small?: string }
    card_faces?: { image_uris?: { small?: string } }[]
  }
  return data.image_uris?.small ?? data.card_faces?.[0]?.image_uris?.small
}
</script>

<template>
  <div class="rounded-lg border border-slate-200 p-3 dark:border-slate-700">
    <form class="flex gap-2" @submit.prevent="search">
      <input
        v-model="query"
        type="search"
        placeholder="Search Scryfall (e.g. sol ring)…"
        class="flex-1 rounded border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800"
      />
      <button
        type="submit"
        :disabled="busy"
        class="rounded bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-50"
      >
        {{ busy ? "Searching…" : "Search" }}
      </button>
    </form>

    <p v-if="error" class="mt-2 text-sm text-red-600">{{ error }}</p>

    <ul v-if="results.length" class="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4 md:grid-cols-6">
      <li v-for="card in results" :key="card.scryfall_id">
        <button
          type="button"
          class="group w-full text-left"
          :title="`Add ${card.name}`"
          @click="emit('add', card)"
        >
          <img
            v-if="thumbnail(card)"
            :src="thumbnail(card)"
            :alt="card.name"
            class="w-full rounded shadow transition group-hover:ring-2 group-hover:ring-brand-500"
          />
          <span class="mt-1 block truncate text-xs text-slate-600 dark:text-slate-300">
            {{ card.name }}
          </span>
        </button>
      </li>
    </ul>
  </div>
</template>
