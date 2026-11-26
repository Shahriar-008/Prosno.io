export interface Bindings {
  DB: D1Database;
  ASSETS?: Fetcher;
  PROSNO_KV?: KVNamespace;
  PROSNO_R2?: R2Bucket;
  BROWSER?: Fetcher;
  SESSION_SECRET?: string;
  ENCRYPTION_KEY?: string;
  GOOGLE_CLIENT_ID?: string;
  GOOGLE_CLIENT_SECRET?: string;
  ADMIN_BOOTSTRAP_SECRET?: string;
  SITE_NAME?: string;
  SITE_URL?: string;
  SUPPORT_EMAIL?: string;
}

export interface AuthUser {
  id: string;
  numeric_id: number;
  username: string;
  email: string;
  display_name: string;
  role: 'admin' | 'editor' | 'teacher';
  is_admin: boolean;
}

export interface AppVariables {
  user: AuthUser | null;
}

export type AppContextEnv = {
  Bindings: Bindings;
  Variables: AppVariables;
};

export interface StudioConfig {
  font: 'hind' | 'noto' | 'tiro' | 'kalpurush';
  paperSize: 'a4' | 'legal';
  columns: 1 | 2 | 3;
  fontSizePx: number;
  marginMm: number;
  omrStyle: boolean;
  showBoardTags: boolean;
  headerPreset: 'board' | 'coaching' | 'minimal';
  instituteName: string;
  instituteSubtitle: string;
  logoUrl: string;
  watermarkText: string;
  watermarkOpacity: number;
}

export interface McqQuestionPayload {
  id?: string | number;
  question_text: string;
  type?: 'simple' | 'complex';
  sub_options?: string[];
  final_prompt?: string;
  answer_options: string[];
  correct_answer: string;
  explanation?: string | null;
  board?: string | null;
  year?: number | null;
  chapter_id?: number | null;
  difficulty?: string | null;
}

export interface SqQuestionPayload {
  id?: string | number;
  question_text: string;
  answer?: string | null;
  marks?: number;
  board?: string | null;
  year?: number | null;
}

export interface CqQuestionPayload {
  id?: string | number;
  stem: string;
  part_ka?: string | null;
  part_kha?: string | null;
  part_ga?: string | null;
  part_gha?: string | null;
  marks_ka?: number;
  marks_kha?: number;
  marks_ga?: number;
  marks_gha?: number;
  total_marks?: number;
  board?: string | null;
  year?: number | null;
}

export interface SqSectionConfig {
  questions: SqQuestionPayload[];
  answer_count: number;
  marks_per_question: number;
}

export interface CqSectionConfig {
  questions: CqQuestionPayload[];
  answer_count: number;
}

export interface PaperConfig {
  title: string;
  class_name?: string;
  subject_name?: string;
  time?: number;
  marks?: number;
  omr_style?: boolean;
  sq_config?: SqSectionConfig | null;
  cq_config?: CqSectionConfig | null;
  studio?: Partial<StudioConfig>;
}

export type OmrSheetVariant = 'institutional' | 'general';
export type OmrBubbleSize = 'small' | 'large';
export type OmrHeaderMode = 'digital' | 'manual';
export type OmrThemeColor =
  | 'rose'
  | 'slate'
  | 'blue'
  | 'green'
  | 'violet'
  | 'orange'
  | 'pink'
  | 'gold';

export interface OmrConfig {
  template_type: 'exam_sheet_v1';
  sheet_variant: OmrSheetVariant;
  question_count: number;
  answer_columns: number;
  theme_color: OmrThemeColor;
  bubble_size: OmrBubbleSize;
  header_mode: OmrHeaderMode;
  header: {
    title: string;
    subtitle: string;
    institution: string;
  };
  fields: {
    roll: boolean;
    set_code: boolean;
    subject_code: boolean;
  };
  instructions: string[];
}
