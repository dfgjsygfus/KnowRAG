import { ref } from "vue";

const toasts = ref([]);
let nextId = 1;

export function useToast() {
  function showToast(message) {
    const id = nextId;
    nextId += 1;
    const toast = { id, message };
    toasts.value = [...toasts.value, toast];
    setTimeout(() => {
      toasts.value = toasts.value.filter((item) => item.id !== id);
    }, 2600);
  }

  return { toasts, showToast };
}
