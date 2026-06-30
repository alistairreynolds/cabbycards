// frontend/src/components/PrintingSelector.spec.ts
import { flushPromises, mount } from "@vue/test-utils"
import { afterEach, describe, expect, it, vi } from "vitest"

import * as api from "@/lib/api"
import PrintingSelector from "@/components/PrintingSelector.vue"

describe("PrintingSelector", () => {
  afterEach(() => vi.restoreAllMocks())

  it("loads printings and emits the chosen printing + finish + condition", async () => {
    vi.spyOn(api, "apiFetch").mockResolvedValue([
      { scryfall_id: "s-c21", name: "Sol Ring", data: { set: "c21", finishes: ["nonfoil", "foil"] } },
      { scryfall_id: "s-ltr", name: "Sol Ring", data: { set: "ltr", finishes: ["nonfoil"] } },
    ])
    const wrapper = mount(PrintingSelector, { props: { oracleScryfallId: "s-c21" } })
    await flushPromises()

    await wrapper.find("button[data-test='confirm']").trigger("click")
    const events = wrapper.emitted("select")
    expect(events).toBeTruthy()
    expect(events?.[0][0]).toMatchObject({ scryfall_id: "s-c21", condition: "nm" })
  })
})
