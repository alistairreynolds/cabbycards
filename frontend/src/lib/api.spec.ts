import { afterEach, beforeEach, expect, it, vi } from "vitest"

import { ApiError, apiFetch, getToken, setToken } from "@/lib/api"

function mockFetch(response: Response) {
  const fn = vi.fn().mockResolvedValue(response)
  vi.stubGlobal("fetch", fn)
  return fn
}

function jsonResponse(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  })
}

function headersOf(fetchMock: ReturnType<typeof vi.fn>): Headers {
  return (fetchMock.mock.calls[0][1] as RequestInit).headers as Headers
}

beforeEach(() => localStorage.clear())
afterEach(() => vi.unstubAllGlobals())

it("prefixes /api and returns parsed JSON", async () => {
  const fetchMock = mockFetch(jsonResponse({ ok: true }))
  const data = await apiFetch<{ ok: boolean }>("/auth/me")
  expect(fetchMock).toHaveBeenCalledWith("/api/auth/me", expect.anything())
  expect(data).toEqual({ ok: true })
})

it("attaches a Bearer token when one is stored", async () => {
  setToken("tok123")
  const fetchMock = mockFetch(jsonResponse({}))
  await apiFetch("/auth/me")
  expect(headersOf(fetchMock).get("Authorization")).toBe("Bearer tok123")
})

it("omits Authorization when no token is stored", async () => {
  const fetchMock = mockFetch(jsonResponse({}))
  await apiFetch("/cards/search")
  expect(headersOf(fetchMock).get("Authorization")).toBeNull()
})

it("sets JSON content-type when a body is sent", async () => {
  const fetchMock = mockFetch(jsonResponse({}))
  await apiFetch("/auth/login", { method: "POST", body: JSON.stringify({ a: 1 }) })
  expect(headersOf(fetchMock).get("Content-Type")).toBe("application/json")
})

it("throws ApiError carrying the server detail on non-2xx", async () => {
  mockFetch(jsonResponse({ detail: "Invalid credentials" }, { status: 401 }))
  await expect(
    apiFetch("/auth/login", { method: "POST", body: "{}" }),
  ).rejects.toMatchObject({ status: 401, message: "Invalid credentials" })
})

it("returns undefined for 204 No Content", async () => {
  mockFetch(new Response(null, { status: 204 }))
  expect(await apiFetch("/whatever")).toBeUndefined()
})

it("round-trips and clears the token", () => {
  setToken("abc")
  expect(getToken()).toBe("abc")
  setToken(null)
  expect(getToken()).toBeNull()
})

it("exposes ApiError as an Error subclass", () => {
  expect(new ApiError(500, "boom")).toBeInstanceOf(Error)
})
