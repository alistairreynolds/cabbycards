import { createPinia, setActivePinia } from "pinia"
import { beforeEach, expect, it, vi } from "vitest"

vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(),
  setToken: vi.fn(),
  getToken: vi.fn(() => null),
}))

import { apiFetch, setToken } from "@/lib/api"
import { useAuthStore } from "@/stores/auth"

const mockApi = vi.mocked(apiFetch)
const mockSetToken = vi.mocked(setToken)

const TOKEN = { access_token: "jwt-1", token_type: "bearer" }
const ME = { id: "u1", email: "a@b.com", display_name: null, email_verified: false }

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

it("starts unauthenticated with no user", () => {
  const auth = useAuthStore()
  expect(auth.isAuthenticated).toBe(false)
  expect(auth.user).toBeNull()
})

it("login stores + persists the token and loads the user", async () => {
  mockApi.mockResolvedValueOnce(TOKEN).mockResolvedValueOnce(ME)
  const auth = useAuthStore()

  await auth.login("a@b.com", "pw")

  expect(auth.isAuthenticated).toBe(true)
  expect(mockSetToken).toHaveBeenCalledWith("jwt-1")
  expect(auth.user?.email).toBe("a@b.com")
  expect(mockApi).toHaveBeenCalledWith("/auth/login", expect.objectContaining({ method: "POST" }))
})

it("register sends the turnstile token then logs in", async () => {
  mockApi.mockResolvedValueOnce(TOKEN).mockResolvedValueOnce(ME)
  const auth = useAuthStore()

  await auth.register("c@d.com", "pw12345678", "turnstile-xyz", "Cabby")

  const [, options] = mockApi.mock.calls[0]
  expect(JSON.parse((options as RequestInit).body as string)).toMatchObject({
    email: "c@d.com",
    turnstile_token: "turnstile-xyz",
  })
  expect(auth.isAuthenticated).toBe(true)
})

it("logout clears the token and user", async () => {
  mockApi.mockResolvedValueOnce(TOKEN).mockResolvedValueOnce(ME)
  const auth = useAuthStore()
  await auth.login("a@b.com", "pw")

  auth.logout()

  expect(auth.isAuthenticated).toBe(false)
  expect(auth.user).toBeNull()
  expect(mockSetToken).toHaveBeenLastCalledWith(null)
})
