-- 🚨 SECURITY CRITICAL: ENABLE ROW LEVEL SECURITY (RLS) 🚨
-- Run this in your Supabase SQL Editor to protect your data from public access.

-- 1. Enable RLS on all tables
-- This implicitly denies all public access (anon/authenticated roles) via the Supabase API
-- because no policies exist yet. The Flask app (connected as postgres user) will still have access.

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ai_generator_config ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ai_generator_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.activity_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.classes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.subjects ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chapters ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.generated_papers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cq_questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.question_sets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.generation_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.short_questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.quizzes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.quiz_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bank_questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.teacher_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.teacher_badges ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.publish_prompts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.moderation_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.question_interactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.teacher_library ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.teacher_notifications ENABLE ROW LEVEL SECURITY;

-- 2. Optional: Allow Public Read Access to content?
-- If you want your frontend (React/JS using supabase-js) to read questions directly,
-- you would add policies here. 
-- BUT since your app uses Flask to serve questions, YOU DO NOT NEED PUBLIC POLICIES.
-- Keeping RLS enabled with NO policies is the safest state (Deny All Public).

-- 3. Verify Protection
-- After running this, try accessing https://<project>.supabase.co/rest/v1/users via browser/curl.
-- It should return an empty list [] or error, effectively hiding the data.
