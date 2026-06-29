import { createPinia } from "pinia"
import { createApp } from "vue"

import App from "@/App.vue"
import router from "@/router"
import { useThemeStore } from "@/stores/theme"
import "@/style.css"

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)

// Apply the saved/preferred theme to <html> before mount to avoid a flash.
useThemeStore(pinia).init()

app.use(router).mount("#app")
