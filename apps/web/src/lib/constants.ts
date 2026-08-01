export const APP_NAME = 'AI 文件與知識平台';
export const APP_DESCRIPTION = '仁愛堂 AI 文件與知識平台';

export const DEFAULT_MODEL = 'deepseek-chat';

export const MODELS = [
  { id: 'deepseek-chat', name: 'DeepSeek-V4-Flash', tier: 'primary' },
  { id: 'deepseek-reasoner', name: 'DeepSeek-V4-Pro', tier: 'quality' },
  { id: 'qwen-max', name: 'Qwen3.7 Max', tier: 'premium' },
] as const;

export const PER_PAGE = 20;

export const MEETING_STATUS_OPTIONS = [
  { value: 'pending', label: '待處理' },
  { value: 'transcribing', label: '轉寫中' },
  { value: 'completed', label: '已完成' },
  { value: 'failed', label: '失敗' },
];

export const DOCGEN_STATUS_OPTIONS = [
  { value: 'draft', label: '草稿' },
  { value: 'submitted', label: '已提交' },
  { value: 'approved', label: '已核准' },
  { value: 'rejected', label: '已退回' },
];

export const LANGUAGES = [
  { value: 'yue', label: '廣東話' },
  { value: 'zh', label: '普通話' },
  { value: 'en', label: '英文' },
  { value: 'mixed', label: '混合' },
];
