<!-- frontend/src/components/PrintingSelector.vue -->
<script setup lang="ts">
import { computed, onMounted, ref } from "vue"

import { apiFetch } from "@/lib/api"

interface Printing {
  scryfall_id: string
  name: string
  data: { set?: string; collector_number?: string; finishes?: string[] }
}

const props = defineProps<{ oracleScryfallId: string }>()
const emit = defineEmits<{ select: [{ scryfall_id: string; foil: boolean; condition: string }] }>()

const CONDITIONS = ["nm", "lp", "mp", "hp", "dmg"]

const printings = ref<Printing[]>([])
const selectedId = ref("")
const finish = ref("nonfoil")
const condition = ref("nm")

onMounted(async () => {
  printings.value = await apiFetch<Printing[]>(`/cards/${props.oracleScryfallId}/printings`)
  selectedId.value = printings.value[0]?.scryfall_id ?? props.oracleScryfallId
})

const selected = computed(() => printings.value.find((p) => p.scryfall_id === selectedId.value))
const finishes = computed(() => selected.value?.data.finishes ?? ["nonfoil"])

function confirm(): void {
  emit("select", {
    scryfall_id: selectedId.value,
    foil: finish.value === "foil" || finish.value === "etched",
    condition: condition.value,
  })
}
</script>

<template>
  <div class="space-y-2 rounded border border-slate-200 p-3 dark:border-slate-700">
    <label class="block text-xs">
      Printing
      <select v-model="selectedId" class="mt-1 w-full rounded border px-2 py-1 text-sm dark:bg-slate-800">
        <option v-for="p in printings" :key="p.scryfall_id" :value="p.scryfall_id">
          {{ (p.data.set ?? "?").toUpperCase() }} · {{ p.data.collector_number ?? "" }}
        </option>
      </select>
    </label>
    <label class="block text-xs">
      Finish
      <select v-model="finish" class="mt-1 w-full rounded border px-2 py-1 text-sm dark:bg-slate-800">
        <option v-for="f in finishes" :key="f" :value="f">{{ f }}</option>
      </select>
    </label>
    <label class="block text-xs">
      Condition
      <select v-model="condition" class="mt-1 w-full rounded border px-2 py-1 text-sm dark:bg-slate-800">
        <option v-for="c in CONDITIONS" :key="c" :value="c">{{ c.toUpperCase() }}</option>
      </select>
    </label>
    <button
      type="button"
      data-test="confirm"
      class="w-full rounded bg-brand-500 px-3 py-1.5 text-sm font-medium text-white"
      @click="confirm"
    >
      Add to deck
    </button>
  </div>
</template>
