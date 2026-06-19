import { ref } from "vue";

const isVisible = ref(false);
const message = ref("");
let resolvePromise = null;

export function useConfirm() {
  function confirm(text) {
    message.value = text;
    isVisible.value = true;
    return new Promise((resolve) => {
      resolvePromise = resolve;
    });
  }

  function confirmYes() {
    isVisible.value = false;
    resolvePromise?.(true);
    resolvePromise = null;
  }

  function confirmNo() {
    isVisible.value = false;
    resolvePromise?.(false);
    resolvePromise = null;
  }

  return { isVisible, message, confirm, confirmYes, confirmNo };
}
