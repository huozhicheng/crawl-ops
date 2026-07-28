<script setup lang="ts">
import { NConfigProvider, NMessageProvider, NDialogProvider, zhCN, dateZhCN, type GlobalThemeOverrides } from 'naive-ui'
import { RouterView } from 'vue-router'

// Arco Design 风格主题配置
const themeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#165DFF',
    primaryColorHover: '#4080FF',
    primaryColorPressed: '#0E42D2',
    primaryColorSuppl: '#165DFF',
    successColor: '#00B42A',
    successColorHover: '#23C343',
    successColorPressed: '#009A29',
    warningColor: '#FF7D00',
    warningColorHover: '#FF9A2E',
    warningColorPressed: '#D25F00',
    errorColor: '#F53F3F',
    errorColorHover: '#F76560',
    errorColorPressed: '#CB272D',
    textColor1: '#1D2129',
    textColor2: '#4E5969',
    textColor3: '#86909C',
    dividerColor: '#E5E6EB',
    borderColor: '#E5E6EB',
    borderRadius: '4px',
    borderRadiusSmall: '2px',
    fontFamily: "-apple-system, BlinkMacSystemFont, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', sans-serif",
  },
  Card: {
    borderRadius: '8px',
    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
  },
  Button: {
    borderRadiusMedium: '4px',
  },
  Tag: {
    borderRadius: '4px',
  },
  Statistic: {
    valueFontSize: '28px',
  },
}
</script>

<template>
  <n-config-provider :locale="zhCN" :date-locale="dateZhCN" :theme-overrides="themeOverrides">
    <n-message-provider>
      <n-dialog-provider>
        <RouterView />
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<style>
* {
  box-sizing: border-box;
}

body {
  margin: 0;
  padding: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', sans-serif;
  background-color: #F2F3F5;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* 全局卡片样式 - 自适应宽度 */
.n-card {
  border-radius: 8px !important;
}

/* 数据表格优化 */
.n-data-table {
  font-size: 14px;
}

/* Modal 优化 */
.n-modal {
  border-radius: 8px;
}
</style>
