"""All MVP tables; FEAT-001 §6.1, FEAT-004 §6.3, FEAT-006 §6.4.

LangGraph owns its checkpoint tables in a separate agents.db file.
Distances are metres, lengths millimetres, fuel millilitres and CO2 grams.
"""

import sqlalchemy as sa
from alembic import op

from routepilot.shared.db.types import UtcDateTime, UuidText

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def _id() -> sa.Column:
    return sa.Column("id", UuidText(), primary_key=True)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.Column("updated_at", UtcDateTime(), nullable=False),
    ]


def _editable() -> list[sa.Column]:
    return [
        _id(),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        *_timestamps(),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        *_editable(),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("locale", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("failed_logins", sa.Integer(), nullable=False),
        sa.Column("locked_until", UtcDateTime()),
        sa.Column("last_login_at", UtcDateTime()),
        sa.CheckConstraint("email = lower(email)", name="ck_users_email_lower"),
        sa.CheckConstraint("role IN ('admin', 'dispatcher', 'demo')", name="ck_users_role"),
        sa.CheckConstraint("locale IN ('en', 'pl')", name="ck_users_locale"),
    )
    op.create_table(
        "sessions",
        _id(),
        sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
        sa.Column(
            "user_id", UuidText(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("expires_at", UtcDateTime(), nullable=False),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.Column("ip_hash", sa.Text(), nullable=False),
        sa.Column("ua_hash", sa.Text(), nullable=False),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_table(
        "cost_profiles",
        *_editable(),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("currency", sa.Text(3), nullable=False),
        sa.Column("fuel_price_minor_per_l", sa.Integer(), nullable=False),
        sa.Column("driver_cost_minor_per_hour", sa.Integer(), nullable=False),
        sa.Column("vehicle_cost_minor_per_km", sa.Integer(), nullable=False),
        sa.Column("accommodation_minor", sa.Integer(), nullable=False),
        sa.Column("per_diem", sa.JSON(), nullable=False),
        sa.Column("tolls", sa.JSON(), nullable=False),
        sa.Column("fx_rates", sa.JSON(), nullable=False),
        sa.Column("min_profit_minor", sa.Integer(), nullable=False),
        sa.Column("min_margin_pct", sa.Text(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "vehicles",
        *_editable(),
        sa.Column("label", sa.Text(), nullable=False, unique=True),
        sa.Column("vehicle_type", sa.Text(), nullable=False),
        sa.Column("body_type", sa.Text(), nullable=False),
        sa.Column("inner_length_mm", sa.Integer()),
        sa.Column("inner_width_mm", sa.Integer()),
        sa.Column("inner_height_mm", sa.Integer()),
        sa.Column("pallet_places", sa.Integer(), nullable=False),
        sa.Column("layout_template", sa.Text(), nullable=False),
        sa.Column("side_access", sa.Text(), nullable=False),
        sa.Column("payload_kg", sa.Integer(), nullable=False),
        sa.Column("gvw_kg", sa.Integer(), nullable=False),
        sa.Column("sleeper_cab", sa.Boolean(), nullable=False),
        sa.Column("fuel_l_per_100km_empty_x10", sa.Integer(), nullable=False),
        sa.Column("fuel_l_per_100km_full_x10", sa.Integer(), nullable=False),
        sa.Column("fuel_speed_curve", sa.Text(), nullable=False),
        sa.Column("fuel_provenance", sa.Text(), nullable=False),
        sa.Column(
            "cost_profile_id",
            UuidText(),
            sa.ForeignKey("cost_profiles.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "drivers",
        *_editable(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text()),
        sa.Column("home_city", sa.Text(), nullable=False),
        sa.Column("home_country", sa.Text(2), nullable=False),
        sa.Column("home_lat", sa.REAL(), nullable=False),
        sa.Column("home_lon", sa.REAL(), nullable=False),
        sa.Column("default_rules_profile", sa.Text(), nullable=False),
        sa.Column(
            "vehicle_id", UuidText(), sa.ForeignKey("vehicles.id", ondelete="RESTRICT"), unique=True
        ),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", UtcDateTime()),
    )
    op.create_table(
        "driver_states",
        _id(),
        sa.Column(
            "driver_id", UuidText(), sa.ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("valid_from", UtcDateTime(), nullable=False),
        sa.Column("current_city", sa.Text()),
        sa.Column("current_lat", sa.REAL(), nullable=False),
        sa.Column("current_lon", sa.REAL(), nullable=False),
        sa.Column("available_from", UtcDateTime(), nullable=False),
        sa.Column("work_today_min", sa.Integer(), nullable=False),
        sa.Column("drive_today_min", sa.Integer(), nullable=False),
        sa.Column("work_since_break_min", sa.Integer(), nullable=False),
        sa.Column("drive_since_break_min", sa.Integer(), nullable=False),
        sa.Column("work_week_min", sa.Integer(), nullable=False),
        sa.Column("drive_week_min", sa.Integer(), nullable=False),
        sa.Column("drive_prev_week_min", sa.Integer(), nullable=False),
        sa.Column("last_daily_rest_end", UtcDateTime()),
        sa.Column("last_weekly_rest_end", UtcDateTime()),
        sa.Column("home_by", UtcDateTime()),
        sa.Column("source", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "work_today_min >= 0 AND drive_today_min >= 0 AND work_since_break_min >= 0 "
            "AND drive_since_break_min >= 0 AND work_week_min >= 0 "
            "AND drive_week_min >= 0 AND drive_prev_week_min >= 0",
            name="ck_driver_states_counters",
        ),
    )
    op.create_index(
        "ix_driver_states_driver_valid_from",
        "driver_states",
        ["driver_id", sa.text("valid_from DESC")],
    )
    op.create_table(
        "import_batches",
        _id(),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("started_at", UtcDateTime(), nullable=False),
        sa.Column("finished_at", UtcDateTime()),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("counts", sa.JSON(), nullable=False),
    )
    op.create_table(
        "raw_freight_records",
        _id(),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_offer_id", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("payload_sha256", sa.Text(), nullable=False),
        sa.Column("fetched_at", UtcDateTime(), nullable=False),
        sa.Column(
            "import_batch_id",
            UuidText(),
            sa.ForeignKey("import_batches.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("retention_until", UtcDateTime()),
        sa.UniqueConstraint(
            "source", "source_offer_id", "payload_sha256", name="uq_raw_freight_source_payload"
        ),
    )
    op.create_table(
        "freight_offers",
        *_editable(),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_offer_id", sa.Text(), nullable=False),
        sa.Column(
            "raw_record_id",
            UuidText(),
            sa.ForeignKey("raw_freight_records.id", ondelete="SET NULL"),
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("public_remark", sa.Text()),
        sa.Column("revenue_amount_minor", sa.Integer()),
        sa.Column("revenue_currency", sa.Text(3)),
        sa.Column("weight_kg", sa.Integer()),
        sa.Column("pallet_count", sa.Integer()),
        sa.Column("pallet_type", sa.Text()),
        sa.Column("loading_length_mm", sa.Integer()),
        sa.Column("required_body_types", sa.JSON(), nullable=False),
        sa.Column("required_vehicle_types", sa.JSON(), nullable=False),
        sa.Column("completeness_score", sa.REAL(), nullable=False),
        sa.Column("missing_fields", sa.JSON(), nullable=False),
        sa.Column("quality_flags", sa.JSON(), nullable=False),
        sa.Column("field_provenance", sa.JSON(), nullable=False),
        sa.Column("retention_until", UtcDateTime()),
        sa.UniqueConstraint("source", "source_offer_id", name="uq_freight_offers_source"),
        sa.CheckConstraint(
            "status IN ('open', 'assigned', 'expired', 'withdrawn')",
            name="ck_freight_offers_status",
        ),
    )
    op.create_table(
        "freight_stops",
        _id(),
        sa.Column(
            "offer_id",
            UuidText(),
            sa.ForeignKey("freight_offers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("stop_type", sa.Text(), nullable=False),
        sa.Column("city", sa.Text(), nullable=False),
        sa.Column("postal_code", sa.Text()),
        sa.Column("country_code", sa.Text(2), nullable=False),
        sa.Column("lat", sa.REAL()),
        sa.Column("lon", sa.REAL()),
        sa.Column("timezone", sa.Text(), nullable=False),
        sa.Column("window_start", UtcDateTime(), nullable=False),
        sa.Column("window_end", UtcDateTime(), nullable=False),
        sa.Column("service_minutes", sa.Integer(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.UniqueConstraint("offer_id", "sequence", name="uq_freight_stops_sequence"),
        sa.CheckConstraint("window_start <= window_end", name="ck_freight_stops_window"),
    )
    op.create_table(
        "optimization_jobs",
        _id(),
        *_timestamps(),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("objectives", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), unique=True),
        sa.Column("input_sha256", sa.Text(), nullable=False),
        sa.Column("request", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON()),
        sa.Column("solver_version", sa.Text(), nullable=False),
        sa.Column("progress", sa.JSON(), nullable=False),
        sa.Column("stats", sa.JSON(), nullable=False),
        sa.Column("error", sa.JSON()),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("heartbeat_at", UtcDateTime()),
        sa.Column(
            "requested_by",
            UuidText(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("started_at", UtcDateTime()),
        sa.Column("finished_at", UtcDateTime()),
    )
    op.create_table(
        "route_plans",
        _id(),
        sa.Column(
            "job_id",
            UuidText(),
            sa.ForeignKey("optimization_jobs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "driver_id",
            UuidText(),
            sa.ForeignKey("drivers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("variant", sa.Text(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("offer_ids", sa.JSON(), nullable=False),
        sa.Column("rules_profile", sa.Text(), nullable=False),
        sa.Column("revenue_minor", sa.Integer(), nullable=False),
        sa.Column("cost_total_minor", sa.Integer(), nullable=False),
        sa.Column("net_profit_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.Text(3), nullable=False),
        sa.Column("margin_pct", sa.Text(), nullable=False),
        sa.Column("distance_m", sa.Integer(), nullable=False),
        sa.Column("empty_m", sa.Integer(), nullable=False),
        sa.Column("fuel_ml", sa.Integer(), nullable=False),
        sa.Column("co2_g", sa.Integer(), nullable=False),
        sa.Column("duration_min", sa.Integer(), nullable=False),
        sa.Column("work_min", sa.Integer(), nullable=False),
        sa.Column("drive_min", sa.Integer(), nullable=False),
        sa.Column("wait_min", sa.Integer(), nullable=False),
        sa.Column("finish_at", UtcDateTime(), nullable=False),
        sa.Column("home_reached", sa.Boolean(), nullable=False),
        sa.Column("risk_level", sa.Text(), nullable=False),
        sa.Column("calculation", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("fleet_role", sa.JSON(), nullable=False),
        sa.Column("geometry", sa.JSON()),
    )
    op.create_index("ix_route_plans_job_driver", "route_plans", ["job_id", "driver_id"])
    op.create_table(
        "route_stops",
        _id(),
        sa.Column(
            "route_plan_id",
            UuidText(),
            sa.ForeignKey("route_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("offer_id", UuidText(), sa.ForeignKey("freight_offers.id", ondelete="RESTRICT")),
        sa.Column("lat", sa.REAL(), nullable=False),
        sa.Column("lon", sa.REAL(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("arrival_at", UtcDateTime(), nullable=False),
        sa.Column("wait_min", sa.Integer(), nullable=False),
        sa.Column("service_start_at", UtcDateTime(), nullable=False),
        sa.Column("departure_at", UtcDateTime(), nullable=False),
        sa.Column("leg_m", sa.Integer(), nullable=False),
        sa.Column("leg_drive_min", sa.Integer(), nullable=False),
        sa.Column("load_pallet_eq_after", sa.Text(), nullable=False),
        sa.Column("load_kg_after", sa.Integer(), nullable=False),
        sa.Column("work_today_min", sa.Integer(), nullable=False),
        sa.Column("drive_today_min", sa.Integer(), nullable=False),
        sa.Column("work_since_break_min", sa.Integer(), nullable=False),
        sa.Column("drive_since_break_min", sa.Integer(), nullable=False),
        sa.UniqueConstraint("route_plan_id", "sequence", name="uq_route_stops_sequence"),
    )
    op.create_table(
        "agent_threads",
        *_editable(),
        sa.Column(
            "user_id", UuidText(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("title", sa.Text(), nullable=False),
    )
    op.create_table(
        "agent_runs",
        _id(),
        sa.Column(
            "thread_id",
            UuidText(),
            sa.ForeignKey("agent_threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("user_message", sa.Text(), nullable=False),
        sa.Column("final_answer", sa.JSON()),
        sa.Column("idempotency_key", sa.Text(), unique=True),
        sa.Column("model_policy", sa.JSON(), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False),
        sa.Column("tokens_out", sa.Integer(), nullable=False),
        sa.Column("cost_estimate_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.Text(3), nullable=False),
        sa.Column("error", sa.JSON()),
        sa.Column("started_at", UtcDateTime()),
        sa.Column("finished_at", UtcDateTime()),
        sa.Column("created_at", UtcDateTime(), nullable=False),
    )
    op.create_index("ix_agent_runs_thread_created", "agent_runs", ["thread_id", "created_at"])
    op.create_table(
        "agent_steps",
        _id(),
        sa.Column(
            "run_id", UuidText(), sa.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("agent", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("tool_name", sa.Text()),
        sa.Column("input_summary", sa.JSON(), nullable=False),
        sa.Column("output_summary", sa.JSON()),
        sa.Column("tokens", sa.JSON()),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("status", sa.Text(), nullable=False),
        sa.UniqueConstraint("run_id", "seq", name="uq_agent_steps_run_seq"),
    )
    op.create_table(
        "approval_requests",
        _id(),
        sa.Column(
            "run_id", UuidText(), sa.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("interrupt_id", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("decided_by", UuidText(), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("decided_at", UtcDateTime()),
        sa.Column("expires_at", UtcDateTime(), nullable=False),
    )
    op.create_table(
        "assignments",
        *_editable(),
        sa.Column(
            "route_plan_id",
            UuidText(),
            sa.ForeignKey("route_plans.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "driver_id",
            UuidText(),
            sa.ForeignKey("drivers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "approved_by",
            UuidText(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("approved_at", UtcDateTime(), nullable=False),
        sa.Column("agent_run_id", UuidText(), sa.ForeignKey("agent_runs.id", ondelete="RESTRICT")),
        sa.Column("status", sa.Text(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'cancelled')", name="ck_assignments_status"),
    )
    op.create_index("ix_assignments_driver_status", "assignments", ["driver_id", "status"])
    op.create_table(
        "route_explanations",
        _id(),
        sa.Column(
            "route_plan_id",
            UuidText(),
            sa.ForeignKey("route_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("model", sa.Text()),
        sa.Column("prompt_version", sa.Text()),
        sa.Column("input_sha256", sa.Text(), nullable=False),
        sa.Column("output", sa.JSON()),
        sa.Column("grounding_ok", sa.Boolean(), nullable=False),
        sa.Column("tokens", sa.JSON()),
        sa.Column("cost_estimate_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.Text(3), nullable=False),
        sa.Column("error", sa.JSON()),
    )
    op.create_table(
        "routing_cache",
        _id(),
        sa.Column("key", sa.Text(), nullable=False, unique=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("provider_version", sa.Text(), nullable=False),
        sa.Column("created_at", UtcDateTime(), nullable=False),
    )
    op.create_table(
        "audit_events",
        _id(),
        sa.Column("at", UtcDateTime(), nullable=False),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.Text()),
        sa.Column("diff", sa.JSON(), nullable=False),
    )
    op.create_index("ix_audit_events_entity", "audit_events", ["entity_type", "entity_id"])
    op.create_table(
        "app_meta",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("updated_at", UtcDateTime(), nullable=False),
    )


def downgrade() -> None:
    for table in [
        "app_meta",
        "audit_events",
        "routing_cache",
        "route_explanations",
        "assignments",
        "approval_requests",
        "agent_steps",
        "agent_runs",
        "agent_threads",
        "route_stops",
        "route_plans",
        "optimization_jobs",
        "freight_stops",
        "freight_offers",
        "raw_freight_records",
        "import_batches",
        "driver_states",
        "drivers",
        "vehicles",
        "cost_profiles",
        "sessions",
        "users",
    ]:
        op.drop_table(table)
