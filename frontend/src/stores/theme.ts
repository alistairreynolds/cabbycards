import { defineStore } from "pinia"
import { computed, ref } from "vue"

const STORAGE_KEY = "cabbycards.theme"

type Mode = "light" | "dark"

function _preferredMode(): Mode {
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved === "light" || saved === "dark") {
    return saved
  }
  // matchMedia is absent in some test environments — fall back to light.
  const query = window.matchMedia?.("(prefers-color-scheme: dark)")
  return query?.matches ? "dark" : "light"
}

function _apply(mode: Mode): void {
  document.documentElement.classList.toggle("dark", mode === "dark")
}

export const useThemeStore = defineStore("theme", () => {
  const mode = ref<Mode>(_preferredMode())
  const isDark = computed(() => mode.value === "dark")

  function setMode(next: Mode): void {
    mode.value = next
    localStorage.setItem(STORAGE_KEY, next)
    _apply(next)
  }

  function toggle(): void {
    setMode(isDark.value ? "light" : "dark")
  }

  function init(): void {
    // Apply the resolved preference to <html> on app start.
    _apply(mode.value)
  }

  return { mode, isDark, setMode, toggle, init }
})
