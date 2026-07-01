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
    expect(events?.[0][0]).toMatchObject({ scryfall_id: "s-c21", condition: "nm", foil: false })
  })

  it("shows the full set name and a preview image of the selected printing", async () => {
    vi.spyOn(api, "apiFetch").mockResolvedValue([
      {
        scryfall_id: "s-c21",
        name: "Sol Ring",
        data: {
          set: "c21",
          set_name: "Commander 2021",
          collector_number: "263",
          finishes: ["nonfoil"],
          image_uris: { normal: "https://img/sol-c21.jpg" },
        },
      },
    ])
    const wrapper = mount(PrintingSelector, { props: { oracleScryfallId: "s-c21" } })
    await flushPromises()

    expect(wrapper.find("option").text()).toContain("Commander 2021")
    expect(wrapper.find("option").text()).not.toContain("C21 ·")
    const img = wrapper.find("img")
    expect(img.exists()).toBe(true)
    expect(img.attributes("src")).toBe("https://img/sol-c21.jpg")
  })

  it("emits cancel when the cancel button is clicked", async () => {
    vi.spyOn(api, "apiFetch").mockResolvedValue([
      { scryfall_id: "s-c21", name: "Sol Ring", data: { set: "c21", finishes: ["nonfoil"] } },
    ])
    const wrapper = mount(PrintingSelector, { props: { oracleScryfallId: "s-c21" } })
    await flushPromises()

    await wrapper.find("button[data-test='cancel']").trigger("click")
    expect(wrapper.emitted("cancel")).toBeTruthy()
    expect(wrapper.emitted("select")).toBeFalsy()
  })

  it("emits foil: true when the finish select is set to foil", async () => {
    vi.spyOn(api, "apiFetch").mockResolvedValue([
      { scryfall_id: "s-c21", name: "Sol Ring", data: { set: "c21", finishes: ["nonfoil", "foil"] } },
    ])
    const wrapper = mount(PrintingSelector, { props: { oracleScryfallId: "s-c21" } })
    await flushPromises()

    // Three selects in template order: printing (0), finish (1), condition (2)
    const finishSelect = wrapper.findAll("select")[1]
    await finishSelect.setValue("foil")

    await wrapper.find("button[data-test='confirm']").trigger("click")
    const events = wrapper.emitted("select")
    expect(events).toBeTruthy()
    expect(events?.[0][0]).toMatchObject({ scryfall_id: "s-c21", foil: true, condition: "nm" })
  })
})
