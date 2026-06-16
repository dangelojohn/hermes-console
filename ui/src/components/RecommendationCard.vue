<script setup>
import { computed } from 'vue';

const props = defineProps({
  rec: { type: Object, required: true },
  active: { type: Boolean, default: false },
});

const priorityClass = computed(() => {
  switch ((props.rec.priority || '').toLowerCase()) {
    case 'blocker': return 'priority-blocker';
    case 'high':    return 'priority-high';
    case 'low':     return 'priority-low';
    default:        return 'priority-normal';
  }
});

const stateClass = computed(() => {
  switch (props.rec.state) {
    case 'ready':    return 'pill-info';
    case 'approved': return 'pill-ok';
    case 'applied':  return 'pill-ok';
    case 'rejected': return 'pill-err';
    default:         return 'pill-info';
  }
});

const created = computed(() => {
  if (!props.rec.create_date) return '';
  try { return new Date(props.rec.create_date).toLocaleString(); }
  catch { return props.rec.create_date; }
});
</script>

<template>
  <div
    class="card p-3 sm:p-4 hover:shadow-md transition cursor-pointer"
    :class="{ 'ring-2 ring-brand': active }"
  >
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0 flex-1">
        <div class="flex flex-wrap items-center gap-1.5 mb-1">
          <span class="pill" :class="priorityClass">{{ rec.priority || 'normal' }}</span>
          <span class="pill-info" v-if="rec.recommendation_type">{{ rec.recommendation_type }}</span>
          <span class="pill" :class="stateClass">{{ rec.state }}</span>
        </div>
        <h3 class="font-semibold truncate">{{ rec.name || `#${rec.id}` }}</h3>
        <p v-if="rec.summary" class="text-sm text-slate-600 dark:text-slate-400 line-clamp-2 mt-1">
          {{ rec.summary }}
        </p>
      </div>
      <div class="text-right text-xs text-slate-500 shrink-0">
        <div>#{{ rec.id }}</div>
        <div v-if="created" class="mt-1">{{ created }}</div>
      </div>
    </div>
  </div>
</template>
