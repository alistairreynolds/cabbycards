import { createRouter, createWebHistory } from "vue-router"

import { useAuthStore } from "@/stores/auth"
import HomeView from "@/views/HomeView.vue"
import LoginView from "@/views/LoginView.vue"

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "home", component: HomeView, meta: { requiresAuth: true } },
    { path: "/login", name: "login", component: LoginView },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: "login" }
  }
})

export default router
