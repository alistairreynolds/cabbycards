import { defineStore } from "pinia"
import { computed, ref } from "vue"

import { apiFetch, getToken, setToken } from "@/lib/api"

export interface User {
  id: string
  email: string
  display_name: string | null
  email_verified: boolean
}

interface TokenResponse {
  access_token: string
  token_type: string
}

export const useAuthStore = defineStore("auth", () => {
  const token = ref<string | null>(getToken())
  const user = ref<User | null>(null)
  const isAuthenticated = computed(() => token.value !== null)

  function _applyToken(value: string | null): void {
    token.value = value
    setToken(value)
  }

  async function fetchMe(): Promise<void> {
    user.value = await apiFetch<User>("/auth/me")
  }

  async function login(email: string, password: string): Promise<void> {
    const response = await apiFetch<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    })
    _applyToken(response.access_token)
    await fetchMe()
  }

  async function register(
    email: string,
    password: string,
    turnstileToken: string,
    displayName: string | null = null,
  ): Promise<void> {
    const response = await apiFetch<TokenResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify({
        email,
        password,
        display_name: displayName,
        turnstile_token: turnstileToken,
      }),
    })
    _applyToken(response.access_token)
    await fetchMe()
  }

  function logout(): void {
    _applyToken(null)
    user.value = null
  }

  return { token, user, isAuthenticated, login, register, fetchMe, logout }
})
