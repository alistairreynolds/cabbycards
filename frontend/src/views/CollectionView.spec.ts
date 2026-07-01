import { flushPromises, mount } from "@vue/test-utils"
import { createPinia, setActivePinia } from "pinia"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

vi.mock("@/lib/api", () => ({ apiFetch: vi.fn() }))

import AddCardSearch from "@/components/AddCardSearch.vue"
import PrintingSelector from "@/components/PrintingSelector.vue"
import { apiFetch } from "@/lib/api"
import CollectionView from "@/views/CollectionView.vue"

const mockApi = vi.mocked(apiFetch)

function routeApi(path: string): Promise<unknown> {
  if (path === "/collection/locations") {
    return Promise.resolve([{ id: "l1", name: "Unsorted", kind: "storage" }])
  }
  if (path === "/collection") {
    return Promise.resolve([])
  }
  if (path.startsWith("/cards/")) {
    return Promise.resolve([
      { scryfall_id: "s-c21", name: "Sol Ring", data: { set: "c21", finishes: ["nonfoil", "foil"] } },
    ])
  }
  return Promise.resolve(undefined) // POST /collection/add etc.
}

beforeEach(() => {
  setActivePinia(createPinia())
  mockApi.mockImplementation((path: string) => routeApi(path))
})

afterEach(() => vi.restoreAllMocks())

describe("CollectionView add flow", () => {
  it("adds the chosen printing/finish/condition to the active location", async () => {
    const wrapper = mount(CollectionView)
    await flushPromises()

    // Open the add panel.
    const addButton = wrapper.findAll("button").find((b) => b.text() === "Add cards")
    await addButton?.trigger("click")

    // Pick a card in the search — the PrintingSelector should then appear.
    wrapper.findComponent(AddCardSearch).vm.$emit("add", {
      scryfall_id: "s-c21",
      name: "Sol Ring",
      data: {},
    })
    await flushPromises()
    const selector = wrapper.findComponent(PrintingSelector)
    expect(selector.exists()).toBe(true)

    // Choose the foil finish, then confirm.
    await selector.findAll("select")[1].setValue("foil")
    await selector.find("button[data-test='confirm']").trigger("click")
    await flushPromises()

    const addCall = mockApi.mock.calls.find(([path]) => path === "/collection/add")
    expect(addCall).toBeTruthy()
    const body = JSON.parse((addCall?.[1] as RequestInit).body as string)
    expect(body).toMatchObject({
      scryfall_id: "s-c21",
      location_id: "l1",
      quantity: 1,
      foil: true,
      condition: "nm",
    })

    // After adding, the flow returns to a fresh search.
    expect(wrapper.findComponent(PrintingSelector).exists()).toBe(false)
    expect(wrapper.findComponent(AddCardSearch).exists()).toBe(true)
  })

  it("hides the search while a card is being added; cancel restores it", async () => {
    const wrapper = mount(CollectionView)
    await flushPromises()

    const addButton = wrapper.findAll("button").find((b) => b.text() === "Add cards")
    await addButton?.trigger("click")

    wrapper.findComponent(AddCardSearch).vm.$emit("add", {
      scryfall_id: "s-c21",
      name: "Sol Ring",
      data: {},
    })
    await flushPromises()

    // Searching for a different card mid-add breaks the flow, so the search is
    // hidden until the pending add is confirmed or cancelled.
    expect(wrapper.findComponent(AddCardSearch).exists()).toBe(false)
    const selector = wrapper.findComponent(PrintingSelector)
    expect(selector.exists()).toBe(true)

    await selector.find("button[data-test='cancel']").trigger("click")
    await flushPromises()

    expect(wrapper.findComponent(PrintingSelector).exists()).toBe(false)
    expect(wrapper.findComponent(AddCardSearch).exists()).toBe(true)
    expect(mockApi.mock.calls.some(([path]) => path === "/collection/add")).toBe(false)
  })
})
