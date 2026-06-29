import { createPinia, setActivePinia } from "pinia"
import { beforeEach, expect, it } from "vitest"

import { useThemeStore } from "@/stores/theme"

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
  document.documentElement.classList.remove("dark")
})

it("defaults to light when nothing is saved", () => {
  expect(useThemeStore().isDark).toBe(false)
})

it("toggle flips mode, persists it, and applies the dark class", () => {
  const theme = useThemeStore()

  theme.toggle()
  expect(theme.isDark).toBe(true)
  expect(localStorage.getItem("cabbycards.theme")).toBe("dark")
  expect(document.documentElement.classList.contains("dark")).toBe(true)

  theme.toggle()
  expect(theme.isDark).toBe(false)
  expect(document.documentElement.classList.contains("dark")).toBe(false)
})

it("reads a saved preference on creation", () => {
  localStorage.setItem("cabbycards.theme", "dark")
  expect(useThemeStore().isDark).toBe(true)
})
