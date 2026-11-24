CREATE TABLE IF NOT EXISTS accounts (
 id bigint PRIMARY KEY, login text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 stripe_customer text UNIQUE, stripe_subscription text UNIQUE, billing_status text NOT NULL DEFAULT 'none'
);
CREATE TABLE IF NOT EXISTS sessions (
 hash text PRIMARY KEY, account_id bigint NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
 expires_at timestamptz NOT NULL
);
CREATE TABLE IF NOT EXISTS projects (
 id uuid PRIMARY KEY, account_id bigint NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
 installation_id bigint NOT NULL, repository_id bigint NOT NULL, repo text NOT NULL,
 base_branch text NOT NULL, workflow_id bigint NOT NULL, auto_propose boolean NOT NULL DEFAULT false,
 health_url text, last_scan timestamptz, next_scan timestamptz NOT NULL DEFAULT now(),
 scan_result jsonb NOT NULL DEFAULT '{}', enabled boolean NOT NULL DEFAULT true,
 UNIQUE(account_id,repository_id)
);
CREATE TABLE IF NOT EXISTS incidents (
 id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 fingerprint text NOT NULL, kind text NOT NULL, status text NOT NULL DEFAULT 'open',
 title text NOT NULL, evidence jsonb NOT NULL, first_seen timestamptz NOT NULL DEFAULT now(),
 last_seen timestamptz NOT NULL DEFAULT now(), UNIQUE(project_id,fingerprint)
);
CREATE TABLE IF NOT EXISTS proposals (
 id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 incident_id uuid NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
 status text NOT NULL DEFAULT 'proposed', patch jsonb NOT NULL, pr_number integer,
 pr_url text, verification jsonb, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS jobs (
 id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 kind text NOT NULL, dedupe text NOT NULL UNIQUE, payload jsonb NOT NULL DEFAULT '{}',
 status text NOT NULL DEFAULT 'queued', attempts int NOT NULL DEFAULT 0, error text,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS job_queue_idx ON jobs(status,created_at);
CREATE TABLE IF NOT EXISTS audit (
 id bigserial PRIMARY KEY, account_id bigint NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
 project_id uuid REFERENCES projects(id) ON DELETE SET NULL,
 action text NOT NULL, detail jsonb NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS deliveries (id text PRIMARY KEY, received_at timestamptz NOT NULL DEFAULT now());
