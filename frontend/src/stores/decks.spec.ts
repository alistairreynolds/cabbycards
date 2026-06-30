import { createPinia, setActivePinia } from "pinia"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import * as api from "@/lib/api"
import { useDecksStore } from "@/stores/decks"

describe("decks store", () => {
  beforeEach(() => setActivePinia(createPinia()))
  afterEach(() => vi.restoreAllMocks())

  it("fetches the deck list", async () => {
    const spy = vi.spyOn(api, "apiFetch").mockResolvedValue([
      { id: "d1", name: "EDH", format: "commander", commander: null, distinct_cards: 0, owned_percent: 0 },
    ])
    const store = useDecksStore()
    await store.fetchDecks()
    expect(spy).toHaveBeenCalledWith("/decks")
    expect(store.decks).toHaveLength(1)
  })

  it("adds a card and stores the returned view", async () => {
    const view = { id: "d1", name: "EDH", format: "commander", commander: null, cards: [], deck_violations: [] }
    const spy = vi.spyOn(api, "apiFetch").mockResolvedValue(view)
    const store = useDecksStore()
    await store.addCard("d1", { scryfall_id: "s1", board: "main", quantity: 1, foil: false, condition: "nm" })
    expect(spy).toHaveBeenCalledWith("/decks/d1/cards", expect.objectContaining({ method: "POST" }))
    expect(store.current?.id).toBe("d1")
  })
})
