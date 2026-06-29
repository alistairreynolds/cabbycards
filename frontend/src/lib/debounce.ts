type Debounced<A extends unknown[]> = ((...args: A) => void) & { cancel: () => void }

/**
 * Delay invoking `fn` until `delayMs` after the last call — the last args win.
 * Used for typeahead search so we hit the API once the user pauses, not per key.
 *
 * See: debounce.spec.ts
 */
export function debounce<A extends unknown[]>(fn: (...args: A) => void, delayMs: number): Debounced<A> {
  let timer: ReturnType<typeof setTimeout> | undefined

  const debounced = (...args: A): void => {
    if (timer !== undefined) {
      clearTimeout(timer)
    }
    timer = setTimeout(() => fn(...args), delayMs)
  }

  debounced.cancel = (): void => {
    if (timer !== undefined) {
      clearTimeout(timer)
      timer = undefined
    }
  }

  return debounced
}
