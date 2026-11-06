def assert_exclusive_editor(host_class, active_groups):
    if host_class == "ci_coarse" and active_groups != 0:
        raise ValueError("ci_coarse allows one editor group at a time")
