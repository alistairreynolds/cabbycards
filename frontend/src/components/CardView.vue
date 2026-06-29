<script setup lang="ts">
defineProps<{
  name: string
  imageUrl?: string | null
}>()
</script>

<template>
  <figure class="flex flex-col gap-1">
    <img
      v-if="imageUrl"
      :src="imageUrl"
      :alt="name"
      class="w-full rounded-lg shadow"
    />
    <figcaption class="text-sm font-medium text-slate-700">{{ name }}</figcaption>
  </figure>
</template>
