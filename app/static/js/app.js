import { computed, createApp, onBeforeUnmount, onMounted, ref } from 'https://unpkg.com/vue@3/dist/vue.esm-browser.prod.js';

const money = new Intl.NumberFormat('en-SG', { style: 'currency', currency: 'SGD' });
const price = cents => cents === 0 ? 'Free' : money.format(cents / 100);
const ASK_CONVERSATION_KEY = 'campusswap-ask-conversation-v1';

async function getJSON(url, signal) {
  const response = await fetch(url, { signal });
  if (!response.ok) {
    const error = new Error('Could not load catalogue');
    error.status = response.status;
    throw error;
  }
  return response.json();
}

function browseApp() {
  createApp({
    setup() {
      const keyword = ref('');
      const category = ref('');
      const categories = ref([]);
      const items = ref([]);
      const loading = ref(true);
      const categoryError = ref(false);
      const listingsError = ref(false);
      let controller;

      const categoryOptions = computed(() => category.value && !categories.value.includes(category.value)
        ? [...categories.value, category.value] : categories.value);
      const status = computed(() => {
        if (loading.value) return 'Loading listings…';
        if (listingsError.value) return 'Listings couldn’t load. Check your connection and select Find items to retry.';
        if (!items.value.length && keyword.value.trim()) {
          return 'No relevant listings found. Try a different search or clear the filters.';
        }
        return items.value.length
          ? `${items.value.length} ${items.value.length === 1 ? 'find' : 'finds'} · Seeded demo catalogue`
          : 'No matching items. Try another keyword or clear the filters.';
      });

      function readURL() {
        const params = new URLSearchParams(location.search);
        keyword.value = (params.get('q') || '').slice(0, 200);
        category.value = (params.get('category') || '').slice(0, 80);
      }
      function filters() {
        const params = new URLSearchParams();
        if (keyword.value.trim()) params.set('q', keyword.value.trim());
        if (category.value) params.set('category', category.value);
        return params;
      }
      function listingHref(listingId) {
        const returnParams = filters();
        return `/listings/${encodeURIComponent(listingId)}?from=browse${returnParams.size ? `&${returnParams}` : ''}`;
      }
      async function load(updateURL = false) {
        if (controller) controller.abort();
        controller = new AbortController();
        const signal = controller.signal;
        const params = filters();
        if (updateURL) history.pushState(null, '', '/' + (params.size ? `?${params}` : ''));
        loading.value = true;
        listingsError.value = false;
        try {
          const endpoint = keyword.value.trim() ? '/api/semantic-listings' : '/api/listings';
          items.value = await getJSON(`${endpoint}?${params}`, signal);
        } catch (loadError) {
          if (loadError.name !== 'AbortError') listingsError.value = true;
        } finally {
          if (!signal.aborted) loading.value = false;
        }
      }
      async function loadCategories() {
        try {
          categories.value = await getJSON('/api/categories');
        } catch {
          categoryError.value = true;
        }
      }
      function submit() { load(true); }
      function chooseCategory() { load(true); }
      function reset() {
        keyword.value = '';
        category.value = '';
        load(true);
      }
      function handlePopstate() {
        readURL();
        load();
      }

      onMounted(async () => {
        readURL();
        await loadCategories();
        window.addEventListener('popstate', handlePopstate);
        load();
      });
      onBeforeUnmount(() => {
        if (controller) controller.abort();
        window.removeEventListener('popstate', handlePopstate);
      });

      return { keyword, category, categoryOptions, items, loading, categoryError, status, price, listingHref, submit, chooseCategory, reset };
    }
  }).mount('#browse-app');
}

function detailApp() {
  createApp({
    setup() {
      const item = ref(null);
      const loading = ref(true);
      const error = ref(null);
      const source = new URLSearchParams(location.search);
      const from = source.get('from');
      const browseParams = new URLSearchParams();
      const query = source.get('q');
      const category = source.get('category');
      if (query && query.length <= 200) browseParams.set('q', query);
      if (category && category.length <= 80) browseParams.set('category', category);
      const fromAsk = from === 'ask';
      const hasBrowseFilters = browseParams.size > 0;
      const backHref = fromAsk ? '/ask' : `/${browseParams.size ? `?${browseParams}` : ''}`;
      const backLabel = fromAsk ? '← Back to Ask CampusSwap' : hasBrowseFilters ? '← Back to results' : '← Back to browse';
      onMounted(async () => {
        const id = location.pathname.split('/').filter(Boolean).pop();
        try {
          item.value = await getJSON(`/api/listings/${encodeURIComponent(id)}`);
          document.title = `${item.value.title} | CampusSwap`;
        } catch (loadError) {
          error.value = loadError.status === 404 ? 'not-found' : 'unavailable';
        } finally {
          loading.value = false;
        }
      });
      return { item, loading, error, price, backHref, backLabel };
    }
  }).mount('#detail-app');
}

function askApp() {
  createApp({
    setup() {
      const question = ref('');
      const messages = ref([]);
      const loading = ref(false);
      const error = ref(false);
      const examples = [
        'What can I get for studying under $30?',
        'Compare the calculators',
        'Which items are in better condition?',
      ];
      let messageId = 0;

      function safeListing(item) {
        if (!item || !Number.isInteger(item.id) || typeof item.title !== 'string') return null;
        return {
          id: item.id,
          title: item.title,
          description: typeof item.description === 'string' ? item.description : '',
          category: typeof item.category === 'string' ? item.category : '',
          price_cents: Number.isInteger(item.price_cents) ? item.price_cents : 0,
          condition: typeof item.condition === 'string' ? item.condition : '',
          location: typeof item.location === 'string' ? item.location : '',
          seller: typeof item.seller === 'string' ? item.seller : '',
          icon: typeof item.icon === 'string' ? item.icon : '',
        };
      }

      function safeMessage(message, index) {
        if (!message || !['user', 'assistant'].includes(message.role) || typeof message.text !== 'string') return null;
        return {
          id: Number.isInteger(message.id) ? message.id : index + 1,
          role: message.role,
          text: message.text.slice(0, 2000),
          listings: message.role === 'assistant' && Array.isArray(message.listings)
            ? message.listings.map(safeListing).filter(Boolean) : [],
          has_more: message.role === 'assistant' && Boolean(message.has_more),
        };
      }

      function saveConversation() {
        try {
          sessionStorage.setItem(ASK_CONVERSATION_KEY, JSON.stringify(messages.value.map(safeMessage).filter(Boolean)));
        } catch {
          // Conversation restoration is optional when browser storage is unavailable.
        }
      }

      function restoreConversation() {
        try {
          const saved = JSON.parse(sessionStorage.getItem(ASK_CONVERSATION_KEY) || '[]');
          if (!Array.isArray(saved)) return;
          messages.value = saved.map(safeMessage).filter(Boolean);
          messageId = messages.value.reduce((highest, message) => Math.max(highest, message.id), 0);
        } catch {
          // Ignore invalid or unavailable browser storage and start a fresh chat.
        }
      }

      async function submit() {
        const text = question.value.trim();
        if (!text || loading.value) return;
        messages.value.push({ id: ++messageId, role: 'user', text });
        saveConversation();
        question.value = '';
        loading.value = true;
        error.value = false;
        try {
          const response = await fetch('/api/catalogue-qa', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question: text }),
          });
          if (!response.ok) throw new Error('Catalogue Q&A unavailable');
          const result = await response.json();
          messages.value.push({
            id: ++messageId,
            role: 'assistant',
            text: result.answer,
            listings: result.listings || [],
            has_more: Boolean(result.has_more),
          });
          saveConversation();
        } catch {
          error.value = true;
        } finally {
          loading.value = false;
        }
      }

      function askExample(prompt) {
        question.value = prompt;
        submit();
      }

      onMounted(restoreConversation);

      return { question, messages, loading, error, examples, price, submit, askExample };
    }
  }).mount('#ask-app');
}

if (document.querySelector('#browse-app')) browseApp();
if (document.querySelector('#detail-app')) detailApp();
if (document.querySelector('#ask-app')) askApp();
