import { createRouter, createWebHistory } from "vue-router"

import { useAuthStore } from "@/stores/auth"
import CollectionView from "@/views/CollectionView.vue"
import DeckBuilderView from "@/views/DeckBuilderView.vue"
import DecksView from "@/views/DecksView.vue"
import LoginView from "@/views/LoginView.vue"
import RegisterView from "@/views/RegisterView.vue"

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "collection", component: CollectionView, meta: { requiresAuth: true } },
    { path: "/decks", name: "decks", component: DecksView, meta: { requiresAuth: true } },
    { path: "/decks/:id", name: "deck", component: DeckBuilderView, meta: { requiresAuth: true } },
    { path: "/login", name: "login", component: LoginView },
    { path: "/register", name: "register", component: RegisterView },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: "login" }
  }
})

export default router
