BEGIN;

CREATE TABLE IF NOT EXISTS phase2_schema_migrations(
  version integer PRIMARY KEY,
  name text NOT NULL,
  applied_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO phase2_schema_migrations(version,name)
VALUES (2,'phase2-wave1-v1')
ON CONFLICT (version) DO UPDATE SET name=EXCLUDED.name;

CREATE TABLE IF NOT EXISTS phase2_workspace_runtime(
  workspace_id uuid PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
  opening_root char(64) NOT NULL,
  state text NOT NULL DEFAULT 'ACTIVE' CHECK(state IN ('ACTIVE','PAUSED','QUARANTINED')),
  revision bigint NOT NULL DEFAULT 1 CHECK(revision >= 1),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS phase2_mission_workspace(
  mission_id uuid PRIMARY KEY REFERENCES missions(id) ON DELETE CASCADE,
  workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  state text NOT NULL CHECK(state IN ('CREATED','PLANNED','QUEUED','RUNNING','WAITING_APPROVAL','PAUSED','SUCCEEDED','FAILED','CANCELLED')),
  plan_root char(64),
  policy_root char(64),
  checkpoint_root char(64),
  artifact_root char(64),
  evidence_root char(64),
  opening_root char(64) NOT NULL,
  revision bigint NOT NULL DEFAULT 1 CHECK(revision >= 1),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS phase2_mission_history(
  seq bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  mission_id uuid NOT NULL REFERENCES phase2_mission_workspace(mission_id) ON DELETE CASCADE,
  workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  event_type text NOT NULL,
  from_state text,
  to_state text NOT NULL,
  evidence jsonb NOT NULL,
  evidence_root char(64) NOT NULL,
  opening_root char(64) NOT NULL,
  revision bigint NOT NULL CHECK(revision >= 1),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS phase2_capability_registry(
  capability_id text PRIMARY KEY,
  owner text NOT NULL,
  wave integer NOT NULL CHECK(wave = 1),
  runtime_kind text NOT NULL,
  risk_class text NOT NULL CHECK(risk_class IN ('low','medium','high','critical')),
  resource_class text NOT NULL CHECK(resource_class IN ('control','cpu','browser','gpu','device','mixed')),
  state text NOT NULL CHECK(state IN ('DECLARED','QUALIFIED','ENABLED','DEGRADED','QUARANTINED','DISABLED')),
  implementation_version text NOT NULL,
  contract_root char(64) NOT NULL,
  opening_root char(64) NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  revision bigint NOT NULL DEFAULT 1 CHECK(revision >= 1),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS phase2_capability_history(
  seq bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  capability_id text NOT NULL REFERENCES phase2_capability_registry(capability_id) ON DELETE CASCADE,
  event_type text NOT NULL,
  from_state text,
  to_state text NOT NULL,
  implementation_version text NOT NULL,
  contract_root char(64) NOT NULL,
  evidence_root char(64) NOT NULL,
  opening_root char(64) NOT NULL,
  revision bigint NOT NULL CHECK(revision >= 1),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_phase2_mission_workspace_workspace_state
  ON phase2_mission_workspace(workspace_id,state);
CREATE INDEX IF NOT EXISTS idx_phase2_mission_history_mission_seq
  ON phase2_mission_history(mission_id,seq);
CREATE INDEX IF NOT EXISTS idx_phase2_capability_registry_state
  ON phase2_capability_registry(state);
CREATE INDEX IF NOT EXISTS idx_phase2_capability_history_capability_seq
  ON phase2_capability_history(capability_id,seq);

COMMIT;
