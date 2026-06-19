<script setup>
import { useConfirm } from "../composables/useConfirm.js";

const { isVisible, message, confirmYes, confirmNo } = useConfirm();
</script>

<template>
  <teleport to="body">
    <div v-if="isVisible" class="confirm-overlay" @click.self="confirmNo">
      <div class="confirm-dialog">
        <div class="confirm-title">确认操作</div>
        <div class="confirm-message">{{ message }}</div>
        <div class="confirm-actions">
          <button class="btn btn-ghost" @click="confirmNo">取消</button>
          <button class="btn btn-danger" @click="confirmYes">确定</button>
        </div>
      </div>
    </div>
  </teleport>
</template>

<style scoped>
.confirm-overlay {
  position: fixed;
  inset: 0;
  background: rgba(60, 40, 20, 0.35);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  display: grid;
  place-items: center;
  z-index: 3000;
}

.confirm-dialog {
  width: min(90vw, 360px);
  background: var(--admin-surface, rgba(255, 251, 247, 0.96));
  border: 1px solid rgba(210, 180, 150, 0.35);
  border-radius: var(--admin-radius-xl, 18px);
  box-shadow: 0 12px 40px rgba(100, 70, 40, 0.22);
  padding: 24px;
}

.confirm-title {
  font: 600 16px/1.3 var(--admin-font-display, -apple-system, BlinkMacSystemFont, "SF Pro Display", sans-serif);
  color: var(--admin-fg, #4a3728);
  margin-bottom: 10px;
}

.confirm-message {
  font: 14px/1.55 var(--admin-font-body, -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif);
  color: var(--admin-fg-secondary, #8b7355);
  margin-bottom: 22px;
}

.confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 9px 18px;
  border: 0;
  border-radius: var(--admin-radius-full, 980px);
  background: rgba(240, 232, 220, 0.7);
  color: var(--admin-fg, #4a3728);
  font: 590 13px/1.3 var(--admin-font-body, -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif);
  cursor: pointer;
  transition: all 0.18s ease;
  white-space: nowrap;
}

.btn:hover {
  background: rgba(220, 200, 180, 0.5);
  transform: translateY(-1px);
}

.btn-ghost {
  background: transparent;
  color: var(--admin-fg-secondary, #8b7355);
}

.btn-ghost:hover {
  background: rgba(180, 140, 100, 0.08);
  color: var(--admin-fg, #4a3728);
}

.btn-danger {
  background: rgba(255, 240, 238, 0.8);
  color: var(--admin-danger, #d47060);
}

.btn-danger:hover {
  background: rgba(240, 210, 200, 0.6);
}
</style>
