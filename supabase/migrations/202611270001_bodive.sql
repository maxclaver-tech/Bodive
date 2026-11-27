begin;
create schema if not exists bodive;
revoke all on schema bodive from public, anon, authenticated, service_role;
set local search_path = bodive;
create table if not exists control (
    id integer primary key check (id = 1),
    stopped integer not null default 0 check (stopped in (0, 1)),
    telegram_offset bigint not null default 0
);
insert into control (id) values (1) on conflict (id) do nothing;

create table if not exists opportunities (
    id text primary key,
    created_at text not null,
    dossier text not null
);
create table if not exists approvals (
    id text primary key,
    kind text not null check (kind in ('claude', 'publish', 'advertise', 'expense')),
    payload text not null,
    digest text not null,
    created_at text not null,
    expires_at text not null,
    max_cents integer not null check (max_cents between 0 and 10000),
    status text not null check (status in ('pending', 'approved', 'rejected', 'claimed', 'done', 'cancelled')),
    decided_by text,
    claimed_at text,
    blocked integer not null default 0 check (blocked in (0, 1)),
    result text
);
create table if not exists ledger (
    reference text primary key,
    kind text not null check (kind in ('expense', 'income')),
    cents integer not null check (cents >= 0),
    approval_id text unique references approvals(id),
    created_at text not null
);
create table if not exists events (
    id text primary key,
    created_at text not null,
    name text not null,
    detail text not null
);

alter table bodive.control enable row level security;
alter table bodive.opportunities enable row level security;
alter table bodive.approvals enable row level security;
alter table bodive.ledger enable row level security;
alter table bodive.events enable row level security;
do $$
begin
    create role bodive_runner nologin;
exception when duplicate_object then
    null;
end $$;

grant usage on schema bodive to bodive_runner;
grant select, update on bodive.control to bodive_runner;
grant select, insert, update on bodive.approvals to bodive_runner;
grant select, insert on bodive.opportunities, bodive.ledger, bodive.events to bodive_runner;

create policy runner_access on bodive.control to bodive_runner using (true);
create policy runner_access on bodive.approvals to bodive_runner using (true);
create policy runner_access on bodive.opportunities to bodive_runner using (true);
create policy runner_access on bodive.ledger to bodive_runner using (true);
create policy runner_access on bodive.events to bodive_runner using (true);
commit;
