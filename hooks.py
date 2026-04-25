import os


def get_plugin_config(default: dict | None = None, **kwargs) -> dict | None:
    """Merge default_config.yaml values into the saved config for any missing keys."""
    if default is None:
        return default
    try:
        from helpers import files
        from helpers import yaml_helper
        default_path = files.get_abs_path("usr/plugins/memex/default_config.yaml")
        if os.path.isfile(default_path):
            defaults = yaml_helper.loads(files.read_file(default_path)) or {}
            for k, v in defaults.items():
                if k not in default:
                    default[k] = v
    except Exception:
        pass
    return default
