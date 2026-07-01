<!-- frontend/src/components/PrintingSelector.vue -->
<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue"

import { apiFetch } from "@/lib/api"

interface Printing {
  scryfall_id: string
  name: string
  data: {
    set?: string
    set_name?: string
    collector_number?: string
    finishes?: string[]
    image_uris?: { normal?: string }
    card_faces?: { image_uris?: { normal?: string } }[]
  }
}

const props = withDefaults(
  defineProps<{ oracleScryfallId: string; confirmLabel?: string }>(),
  { confirmLabel: "Add" },
)
const emit = defineEmits<{
  select: [{ scryfall_id: string; foil: boolean; condition: string }]
  cancel: []
}>()

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

// Front-face image of the chosen printing (double-faced cards keep the image on
// the first face rather than the top-level object).
const previewImage = computed(() => {
  const data = selected.value?.data
  return data?.image_uris?.normal ?? data?.card_faces?.[0]?.image_uris?.normal
})

function printingLabel(printing: Printing): string {
  const setName = printing.data.set_name ?? (printing.data.set ?? "?").toUpperCase()
  const number = printing.data.collector_number
  return number ? `${setName} · #${number}` : setName
}

watch(selectedId, () => {
  finish.value = finishes.value[0] ?? "nonfoil"
})

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
    <img
      v-if="previewImage"
      :src="previewImage"
      :alt="selected?.name"
      class="mx-auto w-40 max-w-full rounded-lg shadow"
    />
    <label class="block text-xs">
      Printing
      <select v-model="selectedId" class="mt-1 w-full rounded border px-2 py-1 text-sm dark:bg-slate-800">
        <option v-for="p in printings" :key="p.scryfall_id" :value="p.scryfall_id">
          {{ printingLabel(p) }}
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
    <div class="flex gap-2">
      <button
        type="button"
        data-test="cancel"
        class="rounded border border-slate-300 px-3 py-1.5 text-sm dark:border-slate-600"
        @click="emit('cancel')"
      >
        Cancel
      </button>
      <button
        type="button"
        data-test="confirm"
        class="flex-1 rounded bg-brand-500 px-3 py-1.5 text-sm font-medium text-white"
        @click="confirm"
      >
        {{ props.confirmLabel }}
      </button>
    </div>
  </div>
</template>
