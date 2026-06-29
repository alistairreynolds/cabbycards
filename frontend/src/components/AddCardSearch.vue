<script setup lang="ts">
import { onUnmounted, ref, watch } from "vue"

import { apiFetch } from "@/lib/api"
import { debounce } from "@/lib/debounce"

interface SearchCard {
  scryfall_id: string
  name: string
  data: Record<string, unknown>
}

const DEBOUNCE_MS = 200

const emit = defineEmits<{ add: [card: SearchCard] }>()

const query = ref("")
const results = ref<SearchCard[]>([])
const busy = ref(false)
const error = ref<string | null>(null)

async function runSearch(): Promise<void> {
  const term = query.value.trim()
  if (!term) {
    results.value = []
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

const debouncedSearch = debounce(() => void runSearch(), DEBOUNCE_MS)

// Live typeahead: search ~200ms after the user pauses; clear immediately if empty.
watch(query, (term) => {
  if (!term.trim()) {
    debouncedSearch.cancel()
    results.value = []
    return
  }
  debouncedSearch()
})

// Enter searches immediately rather than waiting out the debounce.
function searchNow(): void {
  debouncedSearch.cancel()
  void runSearch()
}

onUnmounted(() => debouncedSearch.cancel())

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
    <form @submit.prevent="searchNow">
      <div class="flex items-center gap-2">
        <input
          v-model="query"
          type="search"
          placeholder="Start typing a card name…"
          autocomplete="off"
          class="flex-1 rounded border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800"
        />
        <span v-if="busy" class="text-xs text-slate-500">Searching…</span>
      </div>
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
