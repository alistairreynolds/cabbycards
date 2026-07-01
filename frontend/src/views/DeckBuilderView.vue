<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { useRoute } from "vue-router"

import AddCardSearch from "@/components/AddCardSearch.vue"
import PrintingSelector from "@/components/PrintingSelector.vue"
import { useDecksStore, type DeckCard } from "@/stores/decks"
import type { SearchCard } from "@/types/cards"

const store = useDecksStore()
const route = useRoute()
const deckId = route.params.id as string
const activeBoard = ref("main")

onMounted(() => void store.fetchDeck(deckId))

const TYPE_ORDER = [
  "Creature", "Planeswalker", "Instant", "Sorcery",
  "Artifact", "Enchantment", "Land", "Other",
]

function primaryType(card: DeckCard): string {
  const line = String(card.card.data.type_line ?? "")
  const match = TYPE_ORDER.find((t) => t !== "Other" && line.includes(t))
  return match ?? "Other"
}

const boardCards = computed(() => store.current?.cards.filter((c) => c.board === activeBoard.value) ?? [])

const columns = computed(() => {
  const groups: Record<string, DeckCard[]> = {}
  for (const card of boardCards.value) {
    const type = primaryType(card)
    groups[type] = groups[type] ?? []
    groups[type].push(card)
  }
  return TYPE_ORDER.filter((t) => groups[t]?.length).map((t) => ({ type: t, cards: groups[t] }))
})

// Header shows total copies (summed desired qty), not the distinct-entry count —
// a 100-card deck with 30-odd basics should still read 100.
function columnCount(cards: DeckCard[]): number {
  return cards.reduce((total, card) => total + card.desired_quantity, 0)
}

function ownershipClass(card: DeckCard): string {
  if (card.missing_quantity > 0) return "text-red-600"
  if (card.allocated_quantity < card.desired_quantity) return "text-amber-600"
  return "text-emerald-600"
}

const picked = ref<SearchCard | null>(null)

function onPick(card: SearchCard): void {
  picked.value = card
}

async function onSelectPrinting(payload: { scryfall_id: string; foil: boolean; condition: string }): Promise<void> {
  await store.addCard(deckId, { ...payload, board: activeBoard.value, quantity: 1 })
  picked.value = null
}
</script>

<template>
  <section v-if="store.current" class="mx-auto max-w-6xl p-4">
    <header class="mb-4">
      <h1 class="text-xl font-semibold">{{ store.current.name }}</h1>
      <p class="text-xs text-slate-500">
        {{ store.current.format }}
        <span v-if="store.current.commander"> · {{ store.current.commander.name }}</span>
      </p>
      <ul v-if="store.current.deck_violations.length" class="mt-2 text-xs text-red-600">
        <li v-for="code in store.current.deck_violations" :key="code">⚠ {{ code }}</li>
      </ul>
    </header>

    <nav class="mb-4 flex gap-2 border-b border-slate-200 dark:border-slate-700">
      <button
        v-for="board in ['main', 'side', 'maybe', 'command']"
        :key="board"
        type="button"
        class="px-3 py-2 text-sm capitalize"
        :class="board === activeBoard ? 'border-b-2 border-brand-500 font-medium' : 'text-slate-500'"
        @click="activeBoard = board"
      >
        {{ board }}
      </button>
    </nav>

    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <div v-for="column in columns" :key="column.type">
        <h2 class="mb-2 text-sm font-medium text-slate-600 dark:text-slate-300">
          {{ column.type }} ({{ columnCount(column.cards) }})
        </h2>
        <ul class="space-y-1">
          <li
            v-for="entry in column.cards"
            :key="entry.card.id"
            class="flex items-center justify-between rounded border border-slate-200 px-2 py-1 text-sm dark:border-slate-700"
          >
            <span>{{ entry.desired_quantity }}× {{ entry.card.name }}</span>
            <span class="flex items-center gap-2">
              <span :class="ownershipClass(entry)" class="text-xs">
                {{ entry.allocated_quantity }}/{{ entry.desired_quantity }}
              </span>
              <button
                type="button"
                class="text-xs text-red-600 hover:underline"
                @click="store.removeCard(deckId, entry.card.id, entry.board)"
              >
                ✕
              </button>
            </span>
          </li>
        </ul>
      </div>
    </div>

    <aside class="mt-6">
      <h2 class="mb-2 text-sm font-medium">Add a card</h2>
      <!-- Searching for a different card mid-add breaks the flow, so the
           search is swapped out until the add is confirmed or cancelled. -->
      <AddCardSearch v-if="!picked" :search-path="`/decks/${deckId}/card-search`" @add="onPick" />
      <PrintingSelector
        v-else
        :oracle-scryfall-id="picked.scryfall_id"
        confirm-label="Add to deck"
        @select="onSelectPrinting"
        @cancel="picked = null"
      />
    </aside>
  </section>
</template>
