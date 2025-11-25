<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { Session } from '@supabase/supabase-js'
import DocumentUploader from './components/DocumentUploader.vue'
import DocumentList from './components/DocumentList.vue'
import ChatInterface from './components/ChatInterface.vue'
import AnalysisReport from './components/AnalysisReport.vue'
import AuthModal from './components/AuthModal.vue'
import { Document, ChatLineRound, DataAnalysis, ArrowDown } from '@element-plus/icons-vue'
import { supabase } from './lib/supabase'
import { fetchCurrentUser, setAuthToken, clearAuthToken, type CurrentUser } from './api'

const activeTab = ref('upload')
const currentDocumentId = ref('')
const authDialogVisible = ref(false)
const currentUser = ref<CurrentUser | null>(null)
const session = ref<Session | null>(null)
const loadingUser = ref(true)

const isAuthenticated = computed(() => !!currentUser.value)

const documentListRef = ref<InstanceType<typeof DocumentList> | null>(null)

const handleDocumentUploaded = (id: string) => {
  currentDocumentId.value = id
  activeTab.value = 'chat'
  documentListRef.value?.refreshDocuments?.()
}

const handleDocumentSelected = (documentId: string) => {
  currentDocumentId.value = documentId
  activeTab.value = 'chat'
}

const handleAuthSuccess = async (newSession: Session | null) => {
  authDialogVisible.value = false
  if (!newSession) {
    ElMessage.success('注册成功，请验证邮箱后登录')
    return
  }
  await applySession(newSession)
}

const applySession = async (newSession: Session) => {
  session.value = newSession
  setAuthToken(newSession.access_token)
  await loadCurrentUser()
}

const loadCurrentUser = async () => {
  try {
    const { data } = await fetchCurrentUser()
    currentUser.value = data
  } catch (error) {
    clearAuthToken()
    currentUser.value = null
  } finally {
    loadingUser.value = false
  }
}

const initializeAuth = async () => {
  const { data } = await supabase.auth.getSession()
  if (data.session) {
    await applySession(data.session)
  } else {
    clearAuthToken()
    loadingUser.value = false
  }

  supabase.auth.onAuthStateChange((event, sessionValue) => {
    if (sessionValue) {
      applySession(sessionValue)
    } else if (event === 'SIGNED_OUT') {
      clearAuthState()
    }
  })
}

const clearAuthState = () => {
  clearAuthToken()
  currentUser.value = null
  session.value = null
  currentDocumentId.value = ''
}

const handleLogout = async () => {
  await supabase.auth.signOut()
  clearAuthState()
}

watch(isAuthenticated, (authed) => {
  if (!authed) {
    currentDocumentId.value = ''
    if (activeTab.value !== 'upload') {
      activeTab.value = 'upload'
    }
  }
})

onMounted(() => {
  initializeAuth()
})
</script>

<template>
  <div class="app-wrapper">
    <el-container class="main-container">
      <el-aside width="260px" class="sidebar">
        <div class="brand">
          <div class="logo-icon">⚡</div>
          <div class="brand-text">BlockRAG</div>
        </div>
        
        <div class="nav-menu">
          <div 
            class="nav-item" 
            :class="{ active: activeTab === 'upload' }"
            @click="activeTab = 'upload'"
          >
            <el-icon><Document /></el-icon>
            <span>Document</span>
          </div>
          <div 
            class="nav-item" 
            :class="{ active: activeTab === 'chat', disabled: !isAuthenticated || !currentDocumentId }"
            @click="isAuthenticated && currentDocumentId && (activeTab = 'chat')"
          >
            <el-icon><ChatLineRound /></el-icon>
            <span>Chat Q&A</span>
          </div>
          <div 
            class="nav-item" 
            :class="{ active: activeTab === 'analysis', disabled: !isAuthenticated || !currentDocumentId }"
            @click="isAuthenticated && currentDocumentId && (activeTab = 'analysis')"
          >
            <el-icon><DataAnalysis /></el-icon>
            <span>Analysis</span>
          </div>
        </div>

        <div class="sidebar-footer">
          <p class="status-text" v-if="isAuthenticated">
            <span class="dot online"></span> 已登录
          </p>
          <p class="status-text" v-else>
            <span class="dot offline"></span> 未登录
          </p>
        </div>
      </el-aside>
      
      <el-container>
        <el-header class="app-header">
          <div class="header-content">
            <h2>{{ 
              activeTab === 'upload' ? 'Upload Whitepaper' : 
              activeTab === 'chat' ? 'Interactive Q&A' : 
              'Deep Analysis Report' 
            }}</h2>
            <div class="header-actions">
              <el-skeleton v-if="loadingUser" animated :rows="1" style="width: 160px" />
              <template v-else>
                <div v-if="isAuthenticated" class="user-profile">
                  <el-avatar size="small" src="https://cube.elemecdn.com/3/7c/3ea6beec64369c2642b92c6726f1epng.png" />
                  <el-dropdown trigger="click">
                    <span class="username">
                      {{ currentUser?.email }}
                      <el-icon class="dropdown-icon"><ArrowDown /></el-icon>
                    </span>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item @click="handleLogout">退出登录</el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                </div>
                <el-button v-else type="primary" @click="authDialogVisible = true">登录 / 注册</el-button>
              </template>
            </div>
          </div>
        </el-header>
        
        <el-main class="content-area">
          <transition name="fade" mode="out-in">
            <keep-alive>
              <div v-if="activeTab === 'upload'" class="upload-view">
                <DocumentUploader
                  :is-authenticated="isAuthenticated"
                  @document-uploaded="handleDocumentUploaded"
                  @request-auth="authDialogVisible = true"
                />
                <DocumentList
                  ref="documentListRef"
                  :is-authenticated="isAuthenticated"
                  @document-selected="handleDocumentSelected"
                />
              </div>
              <ChatInterface
                v-else-if="activeTab === 'chat'"
                :document-id="currentDocumentId"
                :is-authenticated="isAuthenticated"
              />
              <AnalysisReport
                v-else
                :document-id="currentDocumentId"
                :is-authenticated="isAuthenticated"
              />
            </keep-alive>
          </transition>
        </el-main>
      </el-container>
    </el-container>

    <AuthModal v-model:visible="authDialogVisible" @authenticated="handleAuthSuccess" />
  </div>
</template>

<style scoped>
.app-wrapper {
  height: 100vh;
  width: 100vw;
  display: flex;
  background-color: #f8f9fb;
}

.main-container {
  height: 100%;
  width: 100%;
}

.sidebar {
  background: white;
  border-right: 1px solid #f0f0f0;
  display: flex;
  flex-direction: column;
  padding: 24px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 48px;
  padding-left: 12px;
}

.logo-icon {
  width: 32px;
  height: 32px;
  background: linear-gradient(135deg, #409eff 0%, #2c3e50 100%);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: bold;
  font-size: 18px;
}

.brand-text {
  font-size: 20px;
  font-weight: 700;
  color: #1a1a1a;
  letter-spacing: -0.5px;
}

.nav-menu {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: 12px;
  cursor: pointer;
  color: #606266;
  font-weight: 500;
  transition: all 0.2s ease;
}

.nav-item:hover:not(.disabled) {
  background-color: #f5f7fa;
  color: #409eff;
}

.nav-item.active {
  background-color: #ecf5ff;
  color: #409eff;
}

.nav-item.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.sidebar-footer {
  padding-top: 20px;
  border-top: 1px solid #f0f0f0;
}

.status-text {
  font-size: 12px;
  color: #909399;
  display: flex;
  align-items: center;
  gap: 8px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.dot.online { background-color: #67c23a; }
.dot.offline { background-color: #909399; }

.app-header {
  background: transparent;
  padding: 0 40px;
  height: 80px;
  display: flex;
  align-items: center;
}

.header-content {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-content h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
}

.user-profile {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 12px;
  background: white;
  border-radius: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}

.username {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
}

.header-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  min-width: 200px;
}

.dropdown-icon {
  margin-left: 4px;
}

.content-area {
  padding: 0 40px 40px;
  overflow-y: auto;
}

.upload-view {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* Transitions */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
