import { defineStore } from "pinia"
import { ref } from "vue"

import { apiFetch } from "@/lib/api"

export interface Location {
  id: string
  name: string
  kind: "storage" | "deck"
}

export interface HoldingCard {
  id: number
  scryfall_id: string
  name: string
  data: Record<string, unknown>
}

export interface Holding {
  id: string
  location_id: string
  quantity: number
  foil: boolean
  condition: string
  card: HoldingCard
}

export const useCollectionStore = defineStore("collection", () => {
  const locations = ref<Location[]>([])
  const holdings = ref<Holding[]>([])

  async function fetchLocations(): Promise<void> {
    locations.value = await apiFetch<Location[]>("/collection/locations")
  }

  async function fetchCollection(): Promise<void> {
    holdings.value = await apiFetch<Holding[]>("/collection")
  }

  async function createLocation(name: string): Promise<Location> {
    const location = await apiFetch<Location>("/collection/locations", {
      method: "POST",
      body: JSON.stringify({ name }),
    })
    locations.value.push(location)
    return location
  }

  async function addCard(
    scryfallId: string,
    locationId: string,
    quantity = 1,
    foil = false,
    condition = "nm",
  ): Promise<void> {
    await apiFetch("/collection/add", {
      method: "POST",
      body: JSON.stringify({
        scryfall_id: scryfallId,
        location_id: locationId,
        quantity,
        foil,
        condition,
      }),
    })
    await fetchCollection()
  }

  async function moveCard(
    cardId: number,
    fromLocationId: string,
    toLocationId: string,
    quantity = 1,
    foil = false,
    condition = "nm",
  ): Promise<void> {
    await apiFetch("/collection/move", {
      method: "POST",
      body: JSON.stringify({
        card_id: cardId,
        from_location_id: fromLocationId,
        to_location_id: toLocationId,
        quantity,
        foil,
        condition,
      }),
    })
    await fetchCollection()
  }

  async function removeHolding(holdingId: string): Promise<void> {
    await apiFetch(`/collection/holdings/${holdingId}`, { method: "DELETE" })
    holdings.value = holdings.value.filter((holding) => holding.id !== holdingId)
  }

  return {
    locations,
    holdings,
    fetchLocations,
    fetchCollection,
    createLocation,
    addCard,
    moveCard,
    removeHolding,
  }
})
