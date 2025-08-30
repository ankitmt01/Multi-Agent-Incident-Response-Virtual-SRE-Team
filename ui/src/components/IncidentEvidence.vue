<script setup lang="ts">
defineProps<{ evidence: Array<{ title: string; content: string; score?: number; uri?: string }> }>()
</script>

<template>
  <div class="space-y-3">
    <div v-for="(e,i) in evidence" :key="i" class="border rounded-xl p-3">
      <div class="flex items-start justify-between gap-3">
        <div>
          <div class="font-semibold">{{ e.title }}</div>
          <div class="text-xs text-gray-500" v-if="e.score !== undefined">score: {{ e.score.toFixed(3) }}</div>
        </div>
        <a v-if="e.uri" :href="e.uri" target="_blank" class="text-sm underline">Open</a>
      </div>
      <pre class="mt-2 text-sm whitespace-pre-wrap">{{ e.content }}</pre>
    </div>
  </div>
</template>
