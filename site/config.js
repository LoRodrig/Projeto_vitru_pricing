// URL do projeto e chave "anon" do Supabase.
// Estes dois valores são feitos para ser públicos (o site é 100% estático,
// sem backend) — a proteção real dos dados é a Row Level Security no banco,
// que só libera leitura para quem estiver autenticado (ver supabase/schema.sql).
// Nunca coloque aqui a service_role key.
window.SUPABASE_URL = "COLOQUE_AQUI_A_PROJECT_URL";
window.SUPABASE_ANON_KEY = "COLOQUE_AQUI_A_ANON_KEY";
