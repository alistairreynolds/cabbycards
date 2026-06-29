import { flushPromises, mount } from "@vue/test-utils"
import { afterEach, beforeEach, expect, it, vi } from "vitest"

vi.mock("@/lib/api", () => ({ apiFetch: vi.fn() }))

import { apiFetch } from "@/lib/api"
import AddCardSearch from "@/components/AddCardSearch.vue"

const mockApi = vi.mocked(apiFetch)
const SOL_RING = { scryfall_id: "s1", name: "Sol Ring", data: {} }

beforeEach(() => {
  vi.useFakeTimers()
  vi.clearAllMocks()
})
afterEach(() => vi.useRealTimers())

it("debounces a burst of typing into a single search after 200ms", async () => {
  mockApi.mockResolvedValue([SOL_RING])
  const input = mount(AddCardSearch).find("input")

  await input.setValue("s")
  await input.setValue("so")
  await input.setValue("sol")
  expect(mockApi).not.toHaveBeenCalled()

  vi.advanceTimersByTime(200)
  await flushPromises()

  expect(mockApi).toHaveBeenCalledTimes(1)
  expect(mockApi).toHaveBeenCalledWith("/cards/search?q=sol")
})

it("clears results and does not search when the query is emptied", async () => {
  mockApi.mockResolvedValue([SOL_RING])
  const wrapper = mount(AddCardSearch)
  await wrapper.find("input").setValue("sol")
  vi.advanceTimersByTime(200)
  await flushPromises()
  expect(wrapper.findAll("li").length).toBeGreaterThan(0)

  mockApi.mockClear()
  await wrapper.find("input").setValue("  ")
  vi.advanceTimersByTime(200)
  await flushPromises()

  expect(mockApi).not.toHaveBeenCalled()
  expect(wrapper.findAll("li")).toHaveLength(0)
})

it("emits add with the chosen card when a result is clicked", async () => {
  mockApi.mockResolvedValue([SOL_RING])
  const wrapper = mount(AddCardSearch)
  await wrapper.find("input").setValue("sol")
  vi.advanceTimersByTime(200)
  await flushPromises()

  await wrapper.find("button[title='Add Sol Ring']").trigger("click")

  expect(wrapper.emitted("add")?.[0]).toEqual([SOL_RING])
})
