<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue";
import { emitTo } from "@tauri-apps/api/event";
import { getCurrentWindow } from "@tauri-apps/api/window";

const params = new URLSearchParams(window.location.search);
const chatSurface = ref(params.get("chatSurface") || "pet");
const petScale = ref(Number(params.get("petScale")) || 1);
const menuSubmenu = ref(null); // 'size' | null

let unlistenBlur = null;

async function sendMenuAction(action, payload = {}) {
  try {
    await emitTo("main", "pet-menu-action", { action, payload });
  } catch {
    // Browser dev mode — main window may not be listening.
  }
  try {
    await getCurrentWindow().close();
  } catch {
    // Already closing.
  }
}

function onEsc(e) {
  if (e.key === "Escape") {
    getCurrentWindow().close().catch(() => {});
  }
}

onMounted(async () => {
  document.addEventListener("keydown", onEsc);
  try {
    const win = getCurrentWindow();
    unlistenBlur = await win.onFocusChanged(({ payload }) => {
      if (!payload) win.close().catch(() => {});
    });
  } catch {
    // Browser dev mode — no Tauri window API.
  }
});

onBeforeUnmount(() => {
  document.removeEventListener("keydown", onEsc);
  if (unlistenBlur) unlistenBlur();
});
</script>

<template>
  <main class="menu-window">
    <nav class="context-menu visible">
      <div class="ctx-item" @click="sendMenuAction('open-admin')">
        <span class="ctx-icon">⚙️</span> 打开管理台
      </div>
      <div class="ctx-item" @click="sendMenuAction('toggle-chat')">
        <span class="ctx-icon">{{ chatSurface === 'pet' ? '💬' : '🔇' }}</span>
        {{ chatSurface === 'pet' ? '打开输入框' : '关闭输入框' }}
      </div>
      <div class="ctx-item" @click="sendMenuAction('open-full')">
        <span class="ctx-icon">📖</span> 打开完整聊天
      </div>
      <div class="ctx-sep"></div>
      <div
        class="ctx-item ctx-has-sub"
        :class="{ 'sub-open': menuSubmenu === 'size' }"
        @click.stop="menuSubmenu = menuSubmenu === 'size' ? null : 'size'"
      >
        <span class="ctx-icon">📏</span> 调整大小
        <span class="ctx-arrow">▸</span>
        <div v-if="menuSubmenu === 'size'" class="ctx-submenu" @click.stop>
          <div
            class="ctx-item"
            :class="{ active: petScale === 0.8 }"
            @click.stop="sendMenuAction('set-scale', { scale: 0.8 })"
          >🐕 小</div>
          <div
            class="ctx-item"
            :class="{ active: petScale === 1 }"
            @click.stop="sendMenuAction('set-scale', { scale: 1 })"
          >🐕 中</div>
          <div
            class="ctx-item"
            :class="{ active: petScale === 1.2 }"
            @click.stop="sendMenuAction('set-scale', { scale: 1.2 })"
          >🐕 大</div>
          <div
            class="ctx-item"
            :class="{ active: petScale === 1.4 }"
            @click.stop="sendMenuAction('set-scale', { scale: 1.4 })"
          >🐕 特大</div>
        </div>
      </div>
      <div class="ctx-sep"></div>
      <div class="ctx-item danger" @click="sendMenuAction('exit')">
        <span class="ctx-icon">🚪</span> 退出
      </div>
    </nav>
  </main>
</template>

<style scoped>
/* ---- Glass-morphism context menu (standalone window) ---- */
.menu-window {
  width: 100vw;
  height: 100vh;
  padding: 4px;
  background: transparent;
  overflow: hidden;
}

.context-menu {
  min-width: 180px;
  max-width: 100%;
  background: rgba(255, 252, 248, 0.99);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border: 0.5px solid rgba(210, 180, 150, 0.35);
  border-radius: 14px;
  box-shadow: 0 12px 40px rgba(140, 100, 60, 0.22);
  padding: 4px;
}

.ctx-item {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 8px 14px;
  border-radius: 7px;
  font-size: 13px;
  color: #4a3728;
  cursor: pointer;
  transition: background 0.1s;
  font-weight: 500;
  position: relative;
  white-space: nowrap;
}

.ctx-item:hover {
  background: rgba(232, 150, 122, 0.12);
  color: #e8967a;
}

.ctx-item.danger {
  color: #c06040;
}

.ctx-item.danger:hover {
  background: rgba(200, 100, 60, 0.1);
  color: #c06040;
}

.ctx-item.active {
  background: rgba(232, 150, 122, 0.15);
  color: #e8967a;
  font-weight: 600;
}

.ctx-icon {
  width: 20px;
  text-align: center;
  flex-shrink: 0;
  font-size: 14px;
}

.ctx-arrow {
  margin-left: auto;
  font-size: 10px;
  color: #8b7355;
}

.ctx-has-sub.sub-open {
  background: rgba(232, 150, 122, 0.12);
  color: #e8967a;
}

.ctx-sep {
  height: 1px;
  background: rgba(0, 0, 0, 0.06);
  margin: 3px 8px;
}

/* Submenu */
.ctx-submenu {
  position: absolute;
  left: calc(100% + 4px);
  top: -4px;
  min-width: 120px;
  background: rgba(255, 252, 248, 0.99);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border: 0.5px solid rgba(210, 180, 150, 0.35);
  border-radius: 14px;
  box-shadow: 0 12px 40px rgba(140, 100, 60, 0.22);
  padding: 4px;
}
</style>
