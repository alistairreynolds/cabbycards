<script setup lang="ts">
import { computed, onMounted, ref } from "vue"

import AddCardSearch from "@/components/AddCardSearch.vue"
import PrintingSelector from "@/components/PrintingSelector.vue"
import { type Holding, useCollectionStore } from "@/stores/collection"
import type { SearchCard } from "@/types/cards"

const collection = useCollectionStore()

const ALL = "all"
const selectedLocationId = ref<string>(ALL)
const newLocationName = ref("")
const showAdd = ref(false)
const picked = ref<SearchCard | null>(null)

onMounted(async () => {
  await Promise.all([collection.fetchLocations(), collection.fetchCollection()])
})

const visibleHoldings = computed<Holding[]>(() => {
  if (selectedLocationId.value === ALL) {
    return collection.holdings
  }
  return collection.holdings.filter((h) => h.location_id === selectedLocationId.value)
})

function thumbnail(holding: Holding): string | undefined {
  const data = holding.card.data as {
    image_uris?: { normal?: string }
    card_faces?: { image_uris?: { normal?: string } }[]
  }
  return data.image_uris?.normal ?? data.card_faces?.[0]?.image_uris?.normal
}

function onPick(card: SearchCard): void {
  picked.value = card
}

async function onSelectPrinting(
  payload: { scryfall_id: string; foil: boolean; condition: string },
): Promise<void> {
  // "All cards" has no single target, so fall back to the first location.
  const target = selectedLocationId.value === ALL ? collection.locations[0]?.id : selectedLocationId.value
  if (target) {
    await collection.addCard(payload.scryfall_id, target, 1, payload.foil, payload.condition)
  }
  picked.value = null
}

async function createLocation(): Promise<void> {
  const name = newLocationName.value.trim()
  if (!name) {
    return
  }
  await collection.createLocation(name)
  newLocationName.value = ""
}
</script>

<template>
  <div class="grid gap-6 md:grid-cols-[14rem_1fr]">
    <aside>
      <h2 class="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">Locations</h2>
      <ul class="space-y-1">
        <li>
          <button
            type="button"
            class="w-full rounded px-3 py-1.5 text-left text-sm"
            :class="selectedLocationId === ALL ? 'bg-brand-500 text-white' : 'hover:bg-slate-100 dark:hover:bg-slate-800'"
            @click="selectedLocationId = ALL"
          >
            All cards
          </button>
        </li>
        <li v-for="loc in collection.locations" :key="loc.id">
          <button
            type="button"
            class="flex w-full items-center justify-between rounded px-3 py-1.5 text-left text-sm"
            :class="selectedLocationId === loc.id ? 'bg-brand-500 text-white' : 'hover:bg-slate-100 dark:hover:bg-slate-800'"
            @click="selectedLocationId = loc.id"
          >
            <span class="truncate">{{ loc.name }}</span>
            <span class="ml-2 text-xs opacity-70">{{ loc.kind === "deck" ? "deck" : "" }}</span>
          </button>
        </li>
      </ul>
      <form class="mt-3 flex gap-1" @submit.prevent="createLocation">
        <input
          v-model="newLocationName"
          placeholder="New binder…"
          class="min-w-0 flex-1 rounded border border-slate-300 px-2 py-1 text-sm dark:border-slate-600 dark:bg-slate-800"
        />
        <button type="submit" class="rounded bg-slate-200 px-2 text-sm dark:bg-slate-700">+</button>
      </form>
    </aside>

    <section>
      <div class="mb-4 flex items-center justify-between">
        <h1 class="text-2xl font-bold">Collection</h1>
        <button
          type="button"
          class="rounded bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600"
          @click="showAdd = !showAdd"
        >
          {{ showAdd ? "Close" : "Add cards" }}
        </button>
      </div>

      <div v-if="showAdd" class="mb-4">
        <!-- Searching for a different card mid-add breaks the flow, so the
             search is swapped out until the add is confirmed or cancelled. -->
        <AddCardSearch v-if="!picked" @add="onPick" />
        <PrintingSelector
          v-else
          :oracle-scryfall-id="picked.scryfall_id"
          confirm-label="Add to collection"
          @select="onSelectPrinting"
          @cancel="picked = null"
        />
      </div>

      <p v-if="!visibleHoldings.length" class="text-slate-500">
        No cards here yet. Click "Add cards" to search and add some.
      </p>

      <ul v-else class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <li v-for="holding in visibleHoldings" :key="holding.id" class="relative">
          <img
            v-if="thumbnail(holding)"
            :src="thumbnail(holding)"
            :alt="holding.card.name"
            class="w-full rounded-lg shadow"
          />
          <p v-else class="rounded-lg border p-2 text-sm">{{ holding.card.name }}</p>
          <span class="absolute left-1 top-1 rounded bg-black/70 px-1.5 py-0.5 text-xs font-semibold text-white">
            ×{{ holding.quantity }}<span v-if="holding.foil"> ✦</span>
          </span>
          <button
            type="button"
            class="absolute right-1 top-1 rounded bg-black/60 px-1.5 py-0.5 text-xs text-white hover:bg-red-600"
            title="Remove"
            @click="collection.removeHolding(holding.id)"
          >
            ✕
          </button>
        </li>
      </ul>
    </section>
  </div>
</template>
