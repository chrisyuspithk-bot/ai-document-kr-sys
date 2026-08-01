/** Common types shared across the frontend. */

export interface User {
  id: string;
  username: string;
  email: string;
  display_name: string;
  org_id: string;
  org_name?: string;
  roles: string[];
  permissions: string[];
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface Conversation {
  id: string;
  title: string | null;
  assistant_id: string | null;
  created_at: string;
  updated_at: string;
  message_count?: number;
}

export interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  citations: Citation[] | null;
  created_at: string;
}

export interface Citation {
  document_id: string;
  document_title: string;
  chunk_text: string;
  score: number;
}

export interface KnowledgeBase {
  id: string;
  name: string;
  description: string | null;
  is_active: boolean;
  document_count: number;
  created_at: string;
}

export interface Document {
  id: string;
  title: string;
  file_type: string;
  status: string;
  kb_id: string | null;
  created_at: string;
}

export interface DocumentTemplate {
  id: string;
  name: string;
  description: string | null;
  category: string | null;
  file_type: string;
}

export interface GeneratedDocument {
  id: string;
  template_id: string | null;
  title: string;
  status: "draft" | "submitted" | "approved" | "rejected";
  content: string | null;
  created_at: string;
  created_by: string;
}

export interface Meeting {
  id: string;
  title: string;
  description: string | null;
  meeting_date: string | null;
  folder: string | null;
  status: string;
  tags: string[] | null;
  created_at: string;
}

export interface MeetingDetail {
  meeting: Meeting;
  recordings: Recording[];
  transcript: Transcript | null;
  summary: MeetingSummary | null;
}

export interface Recording {
  id: string;
  filename: string;
  file_size: number;
  duration_seconds: number | null;
  format: string | null;
  language: string | null;
  status: string;
  created_at: string;
}

export interface Transcript {
  id: string;
  recording_id: string;
  full_text: string;
  segments: TranscriptSegment[] | null;
  language: string | null;
  created_at: string;
}

export interface TranscriptSegment {
  start: number;
  end: number;
  text: string;
}

export interface MeetingSummary {
  id: string;
  summary: string;
  decisions: string[] | null;
  action_items: ActionItem[] | null;
  key_points: string[] | null;
  created_at: string;
}

export interface ActionItem {
  task: string;
  owner: string;
  deadline: string | null;
}

export interface ApiKey {
  id: string;
  name: string;
  key_prefix: string;
  is_active: boolean;
  permissions: string[] | null;
  last_used_at: string | null;
  expires_at: string | null;
  created_at: string;
}

export interface ApiKeyCreated extends ApiKey {
  raw_key: string;
  message: string;
}

export interface AuditLog {
  id: string;
  action: string;
  actor_user_id: string;
  resource_id: string | null;
  detail: Record<string, unknown> | null;
  created_at: string;
}

export interface AIAssistant {
  id: string;
  name: string;
  description: string | null;
  system_prompt: string;
  model: string;
  kb_ids: string[] | null;
  is_public: boolean;
  web_enabled: boolean;
  created_at: string;
}

export interface AssistantFormData {
  name: string;
  description: string;
  system_prompt: string;
  model: string;
  kb_ids: string[];
  is_public: boolean;
  web_enabled: boolean;
}
