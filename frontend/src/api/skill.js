import request from './request'

// 列出当前用户的所有技能（含启用状态）
export function listSkills() {
  return request.get('/skills')
}

// 启用/禁用某技能
export function toggleSkill(skillKey, enabled) {
  return request.put(`/skills/${encodeURIComponent(skillKey)}`, { enabled })
}

// ---------- 技能市场 ----------

// 列出市场所有可下载技能
export function listMarket({ q = '', category = '' } = {}) {
  const params = {}
  if (q) params.q = q
  if (category) params.category = category
  return request.get('/skills/market', { params })
}

// 安装一个市场技能
export function installMarketSkill(skillKey) {
  return request.post(`/skills/market/install/${encodeURIComponent(skillKey)}`)
}

// 卸载已安装的市场技能
export function uninstallMarketSkill(skillKey) {
  return request.delete(`/skills/market/uninstall/${encodeURIComponent(skillKey)}`)
}
