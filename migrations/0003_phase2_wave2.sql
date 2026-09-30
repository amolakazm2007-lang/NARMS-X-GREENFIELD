BEGIN;

INSERT INTO phase2_schema_migrations(version,name)
VALUES (3,'phase2-wave2-v1')
ON CONFLICT (version) DO UPDATE SET name=EXCLUDED.name;

CREATE TABLE phase2_workers(
  worker_id uuid PRIMARY KEY,
  workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  worker_name text NOT NULL,
  state text NOT NULL CHECK(state IN ('REGISTERED','READY','BUSY','DRAINING','OFFLINE','QUARANTINED')),
  capabilities text[] NOT NULL DEFAULT '{}',
  opening_root char(64) NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  last_heartbeat_at timestamptz NOT NULL DEFAULT now(),
  revision bigint NOT NULL DEFAULT 1 CHECK(revision>=1),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(workspace_id,worker_name)
);

CREATE TABLE phase2_worker_leases(
  lease_id uuid PRIMARY KEY,
  workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  mission_id uuid NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
  job_id uuid NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  worker_id uuid NOT NULL REFERENCES phase2_workers(worker_id) ON DELETE CASCADE,
  capability_id text NOT NULL REFERENCES phase2_capability_registry(capability_id),
  fencing_token bigint NOT NULL CHECK(fencing_token>0),
  state text NOT NULL CHECK(state IN ('ACTIVE','RELEASED','EXPIRED','REVOKED')),
  attempt integer NOT NULL CHECK(attempt>=1),
  max_attempts integer NOT NULL CHECK(max_attempts>=1),
  lease_expires_at timestamptz NOT NULL,
  heartbeat_at timestamptz NOT NULL DEFAULT now(),
  idempotency_key text NOT NULL,
  opening_root char(64) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(job_id,fencing_token),
  UNIQUE(workspace_id,idempotency_key)
);
CREATE UNIQUE INDEX uq_phase2_active_job_lease ON phase2_worker_leases(job_id) WHERE state='ACTIVE';

CREATE TABLE phase2_tool_registry(
  tool_id text PRIMARY KEY,
  capability_id text NOT NULL REFERENCES phase2_capability_registry(capability_id),
  risk_class text NOT NULL CHECK(risk_class IN ('read','write','external_side_effect','privileged')),
  permissions text[] NOT NULL DEFAULT '{}',
  input_schema jsonb NOT NULL,
  output_schema jsonb NOT NULL,
  implementation_version text NOT NULL,
  contract_root char(64) NOT NULL,
  opening_root char(64) NOT NULL,
  enabled boolean NOT NULL DEFAULT false,
  revision bigint NOT NULL DEFAULT 1 CHECK(revision>=1),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE phase2_tool_calls(
  call_id uuid PRIMARY KEY,
  workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  mission_id uuid NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
  job_id uuid NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  lease_id uuid NOT NULL REFERENCES phase2_worker_leases(lease_id) ON DELETE RESTRICT,
  tool_id text NOT NULL REFERENCES phase2_tool_registry(tool_id),
  request_type text NOT NULL,
  request_version integer NOT NULL CHECK(request_version>=1),
  request_payload jsonb NOT NULL,
  request_root char(64) NOT NULL,
  approval_id uuid REFERENCES approvals(id),
  state text NOT NULL CHECK(state IN ('ACCEPTED','RUNNING','SUCCEEDED','FAILED','RETRYABLE','DENIED')),
  result_payload jsonb,
  result_root char(64),
  error_payload jsonb,
  idempotency_key text NOT NULL,
  fencing_token bigint NOT NULL CHECK(fencing_token>0),
  attempt integer NOT NULL DEFAULT 1 CHECK(attempt>=1),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(workspace_id,mission_id,idempotency_key)
);

CREATE TABLE phase2_artifact_objects(
  content_sha256 char(64) PRIMARY KEY,
  size_bytes bigint NOT NULL CHECK(size_bytes>=0),
  media_type text NOT NULL,
  storage_uri text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE phase2_artifact_revisions(
  artifact_revision_id uuid PRIMARY KEY,
  workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  mission_id uuid NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
  logical_artifact_id uuid NOT NULL,
  revision integer NOT NULL CHECK(revision>=1),
  content_sha256 char(64) NOT NULL REFERENCES phase2_artifact_objects(content_sha256),
  provenance jsonb NOT NULL,
  provenance_root char(64) NOT NULL,
  evidence_root char(64) NOT NULL,
  opening_root char(64) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(workspace_id,logical_artifact_id,revision)
);
CREATE TABLE phase2_artifact_edges(
  workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  mission_id uuid NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
  parent_revision_id uuid NOT NULL REFERENCES phase2_artifact_revisions(artifact_revision_id) ON DELETE RESTRICT,
  child_revision_id uuid NOT NULL REFERENCES phase2_artifact_revisions(artifact_revision_id) ON DELETE RESTRICT,
  relation text NOT NULL,
  evidence_root char(64) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(parent_revision_id,child_revision_id),
  CHECK(parent_revision_id<>child_revision_id)
);

CREATE TABLE phase2_wave2_idempotency(
  workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  scope text NOT NULL,
  idempotency_key text NOT NULL,
  request_root char(64) NOT NULL,
  response jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(workspace_id,scope,idempotency_key)
);
CREATE TABLE phase2_wave2_quotas(
  workspace_id uuid PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
  max_active_leases integer NOT NULL DEFAULT 32 CHECK(max_active_leases>=1),
  max_tool_calls_per_mission integer NOT NULL DEFAULT 1000 CHECK(max_tool_calls_per_mission>=1),
  max_artifact_bytes bigint NOT NULL DEFAULT 10737418240 CHECK(max_artifact_bytes>=0),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_phase2_workers_workspace_state ON phase2_workers(workspace_id,state);
CREATE INDEX idx_phase2_worker_leases_job_state ON phase2_worker_leases(job_id,state);
CREATE INDEX idx_phase2_worker_leases_expiry ON phase2_worker_leases(state,lease_expires_at);
CREATE INDEX idx_phase2_tool_calls_mission_state ON phase2_tool_calls(mission_id,state);
CREATE INDEX idx_phase2_artifact_revisions_mission ON phase2_artifact_revisions(mission_id,created_at);
CREATE INDEX idx_phase2_artifact_edges_child ON phase2_artifact_edges(child_revision_id);
COMMIT;
