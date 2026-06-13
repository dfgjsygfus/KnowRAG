<script setup>
import PetChatInput from "./components/PetChatInput.vue";
import PetContextMenu from "./components/PetContextMenu.vue";
import PetMain from "./components/PetMain.vue";

const params = new URLSearchParams(window.location.search);
const view = params.get("view") || "pet-main";
</script>

<template>
  <PetChatInput v-if="view === 'pet-chat'" />
  <PetContextMenu v-else-if="view === 'pet-menu'" />
  <PetMain v-else />
</template>
