-- Schema do projeto de monitoramento de preços EAD.
-- Rode este arquivo inteiro no SQL Editor do seu projeto Supabase.

create table if not exists grupos_educacionais (
    id bigint generated always as identity primary key,
    nome text not null unique
);

create table if not exists grupos_curso (
    id bigint generated always as identity primary key,
    nome text not null unique
);

create table if not exists marcas (
    id bigint generated always as identity primary key,
    nome text not null unique,
    slug_ead text not null,
    grupo_educacional_id bigint references grupos_educacionais(id),
    piloto boolean not null default false
);

create table if not exists pricing_snapshots (
    id bigint generated always as identity primary key,
    marca_id bigint not null references marcas(id),
    curso_nome text not null,
    grupo_curso_id bigint references grupos_curso(id),
    valor numeric(10, 2) not null,
    valor_original numeric(10, 2),
    modalidade text not null default 'EAD',
    origem text not null default 'ead.com.br',
    localizacao text,
    source_url text not null,
    captured_at date not null default current_date,
    created_at timestamptz not null default now()
);

-- Migração idempotente: se a tabela já existia (sem essas colunas), este
-- bloco adiciona sem precisar recriar nada. Seguro rodar de novo.
alter table pricing_snapshots add column if not exists modalidade text not null default 'EAD';
alter table pricing_snapshots add column if not exists origem text not null default 'ead.com.br';
alter table pricing_snapshots add column if not exists desconto boolean
    generated always as (valor_original is not null and valor_original > valor) stored;

create index if not exists idx_pricing_snapshots_marca on pricing_snapshots(marca_id);
create index if not exists idx_pricing_snapshots_captured_at on pricing_snapshots(captured_at);
create index if not exists idx_pricing_snapshots_grupo_curso on pricing_snapshots(grupo_curso_id);

-- Row Level Security: ninguém lê ou escreve sem estar autenticado.
-- Escritas (INSERT/UPDATE) só acontecem via service_role key (que ignora RLS),
-- usada exclusivamente pelo workflow de scraping no GitHub Actions.

alter table grupos_educacionais enable row level security;
alter table grupos_curso enable row level security;
alter table marcas enable row level security;
alter table pricing_snapshots enable row level security;

create policy "leitura para usuarios autenticados" on grupos_educacionais
    for select to authenticated using (true);

create policy "leitura para usuarios autenticados" on grupos_curso
    for select to authenticated using (true);

create policy "leitura para usuarios autenticados" on marcas
    for select to authenticated using (true);

create policy "leitura para usuarios autenticados" on pricing_snapshots
    for select to authenticated using (true);
