import { mount } from "@vue/test-utils"
import { expect, it } from "vitest"

import CardView from "@/components/CardView.vue"

it("renders the card name", () => {
  const wrapper = mount(CardView, { props: { name: "Sol Ring" } })
  expect(wrapper.text()).toContain("Sol Ring")
})

it("renders the image with alt text when a URL is provided", () => {
  const wrapper = mount(CardView, {
    props: { name: "Sol Ring", imageUrl: "https://img.test/sol.png" },
  })
  const img = wrapper.find("img")
  expect(img.exists()).toBe(true)
  expect(img.attributes("src")).toBe("https://img.test/sol.png")
  expect(img.attributes("alt")).toBe("Sol Ring")
})

it("renders no image when no URL is provided", () => {
  const wrapper = mount(CardView, { props: { name: "Mountain" } })
  expect(wrapper.find("img").exists()).toBe(false)
})
