def post_init_hook(env):
    """Idempotent: journals / PKR / policy defaults (also run from data XML before demo)."""
    env["hms.setup"].apply_pakistan_defaults()
