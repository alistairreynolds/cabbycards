import { afterEach, beforeEach, expect, it, vi } from "vitest"

import { debounce } from "@/lib/debounce"

beforeEach(() => vi.useFakeTimers())
afterEach(() => vi.useRealTimers())

it("invokes only once after the delay for a burst of calls", () => {
  const fn = vi.fn()
  const debounced = debounce(fn, 200)

  debounced("a")
  debounced("b")
  debounced("c")
  expect(fn).not.toHaveBeenCalled()

  vi.advanceTimersByTime(200)
  expect(fn).toHaveBeenCalledTimes(1)
  expect(fn).toHaveBeenLastCalledWith("c")
})

it("does not fire before the delay elapses", () => {
  const fn = vi.fn()
  const debounced = debounce(fn, 200)
  debounced()
  vi.advanceTimersByTime(199)
  expect(fn).not.toHaveBeenCalled()
})

it("cancel prevents a pending call", () => {
  const fn = vi.fn()
  const debounced = debounce(fn, 200)
  debounced()
  debounced.cancel()
  vi.advanceTimersByTime(500)
  expect(fn).not.toHaveBeenCalled()
})
