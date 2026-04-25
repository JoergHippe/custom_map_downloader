import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Tuple

if TYPE_CHECKING:
    from qgis.core import QgsApplication
else:
    try:
        from qgis.core import QgsApplication  # type: ignore
    except Exception:
        QgsApplication = object  # type: ignore


REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_NAME = "custom_map_downloader"


def _env_profile_root() -> Optional[Path]:
    custom_config = os.environ.get("QGIS_CUSTOM_CONFIG_PATH", "").strip()
    if custom_config:
        return Path(custom_config) / "profiles"
    appdata = os.environ.get("APPDATA", "").strip()
    if appdata:
        return Path(appdata) / "QGIS" / "QGIS3" / "profiles"
    return None


def deployed_plugin_dir(profile_name: str) -> Path:
    profile_root = _env_profile_root()
    if profile_root is None:
        raise RuntimeError("QGIS profile root could not be resolved from environment.")
    return profile_root / profile_name / "python" / "plugins" / PLUGIN_NAME


def plugin_import_mode() -> str:
    return os.environ.get("CMD_PLUGIN_IMPORT_MODE", "repo").strip().lower() or "repo"


def ensure_plugin_import_path() -> Path:
    mode = plugin_import_mode()
    if mode == "profile":
        profile_name = os.environ.get("CMD_QGIS_PROFILE", os.environ.get("QGIS_PROFILE", "default"))
        plugin_dir = deployed_plugin_dir(profile_name)
        if not plugin_dir.exists():
            raise RuntimeError(f"Deployed plugin directory not found: {plugin_dir}")
        parent = plugin_dir.parent
        sys.path[:] = [entry for entry in sys.path if entry != str(parent)]
        sys.path.insert(0, str(parent))
        # If repo modules were already imported during test discovery, force a
        # clean re-import from the deployed profile path.
        for module_name in list(sys.modules):
            if module_name == PLUGIN_NAME or module_name.startswith(f"{PLUGIN_NAME}."):
                sys.modules.pop(module_name, None)
        return plugin_dir

    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    return REPO_ROOT / PLUGIN_NAME


def detect_qgis_prefix() -> str:
    prefix_env = os.environ.get("QGIS_PREFIX_PATH", "").strip()
    qgis_runtime_prefix = ""
    try:
        qgis_runtime_prefix = str(QgsApplication.prefixPath() or "").strip()
    except Exception:
        qgis_runtime_prefix = ""
    candidates = [
        prefix_env,
        qgis_runtime_prefix,
        "/usr",
        "/usr/local",
        "/usr/lib/qgis",
        r"C:\OSGeo4W64\apps\qgis",
        r"C:\OSGeo4W\apps\qgis",
        r"C:\Program Files\QGIS 3.36.0\apps\qgis",
        r"C:\Program Files\QGIS 3.34.0\apps\qgis",
    ]
    return next((p for p in candidates if p and Path(p).exists()), "")


def init_qgis_app() -> Tuple[Optional["QgsApplication"], bool]:
    if QgsApplication is object:
        return None, False

    app = QgsApplication.instance()
    created = False
    if app is None:
        app = QgsApplication([], False)
        created = True

    already_init = bool(getattr(QgsApplication, "_CMD_INIT_DONE", False))
    if not already_init:
        prefix = detect_qgis_prefix()
        if not prefix:
            raise RuntimeError("QGIS prefix path not found; set QGIS_PREFIX_PATH.")
        QgsApplication.setPrefixPath(prefix, True)
        QgsApplication.initQgis()
        QgsApplication._CMD_INIT_DONE = True

    return app, created
