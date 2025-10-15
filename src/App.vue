<template>
  <div class="app">
    <button @click="createFolder">创建随机文件夹</button>
    <p>{{ message }}</p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import axios from 'axios'

const message = ref('')

const createFolder = async () => {
  try {
    // ✅ 用 /api 而不是 http://api
    const res = await axios.get('/api/create-random-folder')
    message.value = res.data
  } catch (err) {
    message.value = '请求失败: ' + err
  }
}
</script>


<style>
button {
  padding: 10px 20px;
  border-radius: 8px;
  background-color: #4caf50;
  color: white;
  border: none;
  cursor: pointer;
}
button:hover {
  background-color: #45a049;
}
.app {
  margin: 50px;
  font-family: Arial, sans-serif;
}
</style>
