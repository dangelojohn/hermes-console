import { createRouter, createWebHistory } from 'vue-router';
import QueueList from './components/QueueList.vue';
import RecommendationDetail from './components/RecommendationDetail.vue';
import LocalQueueView from './components/LocalQueueView.vue';
import ChatView from './components/ChatView.vue';
import TenantsView from './components/TenantsView.vue';
import AgentsView from './components/AgentsView.vue';

const routes = [
  { path: '/', name: 'queue', component: QueueList },
  { path: '/recommendation/:id', name: 'detail', component: RecommendationDetail, props: true },
  { path: '/chat', name: 'chat', component: ChatView },
  { path: '/chat/:threadId', name: 'chat-thread', component: ChatView, props: true },
  { path: '/queue', name: 'localqueue', component: LocalQueueView },
  { path: '/tenants', name: 'tenants', component: TenantsView },
  { path: '/agents', name: 'agents', component: AgentsView },
  { path: '/:pathMatch(.*)*', redirect: '/' },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 };
  },
});

export default router;
