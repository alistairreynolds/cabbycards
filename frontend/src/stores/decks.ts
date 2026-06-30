import { defineStore } from "pinia"
import { ref } from "vue"

import { apiFetch } from "@/lib/api"
import type { HoldingCard } from "@/stores/collection"

export interface DeckSummary {
  id: string
  name: string
  format: string
  commander: HoldingCard | null
  distinct_cards: number
  owned_percent: number
}

export interface DeckCard {
  card: HoldingCard
  board: string
  desired_quantity: number
  allocated_quantity: number
  owned_elsewhere_quantity: number
  missing_quantity: number
  violations: string[]
}

export interface DeckView {
  id: string
  name: string
  format: string
  commander: HoldingCard | null
  cards: DeckCard[]
  deck_violations: string[]
}

export interface AddDeckCardPayload {
  scryfall_id: string
  board: string
  quantity: number
  foil: boolean
  condition: string
}

export const useDecksStore = defineStore("decks", () => {
  const decks = ref<DeckSummary[]>([])
  const current = ref<DeckView | null>(null)

  async function fetchDecks(): Promise<void> {
    decks.value = await apiFetch<DeckSummary[]>("/decks")
  }

  async function createDeck(
    name: string,
    format = "commander",
    commanderScryfallId: string | null = null,
  ): Promise<DeckView> {
    const view = await apiFetch<DeckView>("/decks", {
      method: "POST",
      body: JSON.stringify({ name, format, commander_scryfall_id: commanderScryfallId }),
    })
    current.value = view
    return view
  }

  async function fetchDeck(id: string): Promise<void> {
    current.value = await apiFetch<DeckView>(`/decks/${id}`)
  }

  async function addCard(deckId: string, payload: AddDeckCardPayload): Promise<void> {
    current.value = await apiFetch<DeckView>(`/decks/${deckId}/cards`, {
      method: "POST",
      body: JSON.stringify(payload),
    })
  }

  async function updateCard(
    deckId: string,
    payload: { card_id: number; board: string; desired_quantity: number },
  ): Promise<void> {
    current.value = await apiFetch<DeckView>(`/decks/${deckId}/cards`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    })
  }

  async function removeCard(deckId: string, cardId: number, board: string): Promise<void> {
    current.value = await apiFetch<DeckView>(
      `/decks/${deckId}/cards/${cardId}?board=${board}`,
      { method: "DELETE" },
    )
  }

  async function setCommander(deckId: string, scryfallId: string): Promise<void> {
    current.value = await apiFetch<DeckView>(`/decks/${deckId}`, {
      method: "PATCH",
      body: JSON.stringify({ commander_scryfall_id: scryfallId }),
    })
  }

  async function deleteDeck(deckId: string): Promise<void> {
    await apiFetch(`/decks/${deckId}`, { method: "DELETE" })
    decks.value = decks.value.filter((deck) => deck.id !== deckId)
  }

  return {
    decks, current,
    fetchDecks, createDeck, fetchDeck, addCard, updateCard, removeCard, setCommander, deleteDeck,
  }
})
