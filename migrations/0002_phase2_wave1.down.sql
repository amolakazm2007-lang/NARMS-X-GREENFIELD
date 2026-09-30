BEGIN;
DROP TABLE IF EXISTS phase2_capability_history CASCADE;
DROP TABLE IF EXISTS phase2_capability_registry CASCADE;
DROP TABLE IF EXISTS phase2_mission_history CASCADE;
DROP TABLE IF EXISTS phase2_mission_workspace CASCADE;
DROP TABLE IF EXISTS phase2_workspace_runtime CASCADE;
DROP TABLE IF EXISTS phase2_schema_migrations CASCADE;
COMMIT;
