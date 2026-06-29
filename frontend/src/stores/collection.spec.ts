import { createPinia, setActivePinia } from "pinia"
import { beforeEach, expect, it, vi } from "vitest"

vi.mock("@/lib/api", () => ({ apiFetch: vi.fn() }))

import { apiFetch } from "@/lib/api"
import { useCollectionStore } from "@/stores/collection"

const mockApi = vi.mocked(apiFetch)

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

it("fetchLocations populates locations", async () => {
  mockApi.mockResolvedValueOnce([{ id: "l1", name: "Unsorted", kind: "storage" }])
  const store = useCollectionStore()
  await store.fetchLocations()
  expect(store.locations).toHaveLength(1)
  expect(store.locations[0].name).toBe("Unsorted")
})

it("addCard posts the card then refreshes the collection", async () => {
  mockApi
    .mockResolvedValueOnce(undefined) // POST /collection/add
    .mockResolvedValueOnce([
      { id: "h1", location_id: "l1", quantity: 2, foil: false, condition: "nm", card: { id: 1, scryfall_id: "s1", name: "Sol Ring", data: {} } },
    ]) // GET /collection
  const store = useCollectionStore()

  await store.addCard("scry-1", "l1", 2)

  const [path, options] = mockApi.mock.calls[0]
  expect(path).toBe("/collection/add")
  expect(JSON.parse((options as RequestInit).body as string)).toMatchObject({
    scryfall_id: "scry-1",
    location_id: "l1",
    quantity: 2,
  })
  expect(store.holdings).toHaveLength(1)
})

it("removeHolding drops the holding locally", async () => {
  mockApi.mockResolvedValue(undefined)
  const store = useCollectionStore()
  store.holdings = [
    { id: "h1", location_id: "l1", quantity: 1, foil: false, condition: "nm", card: { id: 1, scryfall_id: "s1", name: "X", data: {} } },
    { id: "h2", location_id: "l1", quantity: 1, foil: false, condition: "nm", card: { id: 2, scryfall_id: "s2", name: "Y", data: {} } },
  ]

  await store.removeHolding("h1")

  expect(mockApi).toHaveBeenCalledWith("/collection/holdings/h1", { method: "DELETE" })
  expect(store.holdings.map((h) => h.id)).toEqual(["h2"])
})
