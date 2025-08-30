<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from 'vue'
import { connectIncidentStream, type IncEvent } from '../lib/stream'

const props = defineProps<{ incidentId: string }>()
const events = ref<IncEvent[]>([])

let disconnect: (() => void) | null = null

onMounted(() => {
  disconnect = connectIncidentStream(props.incidentId, (e) => {
    events.value.unshift(e)
  })
})
onBeforeUnmount(() => {
  disconnect?.()
})
</script>

<template>
  <div class="rounded-xl border p-3">
    <div class="font-semibold mb-2">Live progress</div>
    <ul class="space-y-1 max-h-56 overflow-auto text-sm">
      <li v-for="(e, i) in events" :key="i" class="grid grid-cols-[110px_1fr] gap-2">
        <span class="text-xs text-gray-500">{{ new Date(e.ts * 1000).toLocaleTimeString() }}</span>
        <span>
          <strong>{{ e.event }}</strong>
          <span v-if="e.data?.name">— {{ e.data.name }}</span>
          <span v-if="e.data?.status"> ({{ e.data.status }})</span>
        </span>
      </li>
    </ul>
  </div>
</template>

<style scoped>
/* minimal styling; adapt to your design system */
</style>
