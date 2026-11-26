"""Version and update trust root embedded by the release build."""
try:
    from ._build_info import APP_VERSION, UPDATE_PUBLIC_KEY
except ImportError:
    try:
        from _build_info import APP_VERSION, UPDATE_PUBLIC_KEY
    except ImportError:
        from importlib.metadata import PackageNotFoundError, version
        try:
            APP_VERSION = version("academic-chat-manager")
        except PackageNotFoundError:
            APP_VERSION = "0.1.0"
        UPDATE_PUBLIC_KEY = ""
