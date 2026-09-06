"""
ServerHelper - Lightweight Multi-Agent & Remote SSH Orchestrator
"""
try:
    from importlib.metadata import version as _pkg_version, PackageNotFoundError
    try:
        __version__ = _pkg_version("argos-agent")
    except PackageNotFoundError:
        __version__ = "0.3.0"
except Exception:
    __version__ = "0.3.0"
