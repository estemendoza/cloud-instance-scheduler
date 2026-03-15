from importlib.metadata import version as pkg_version, PackageNotFoundError
import tomllib
import pathlib

try:
    APP_VERSION = pkg_version("cloud-instance-scheduler")
except PackageNotFoundError:
    try:
        _pyproject = pathlib.Path(__file__).parent.parent.parent / "pyproject.toml"
        with open(_pyproject, "rb") as _f:
            APP_VERSION = tomllib.load(_f)["tool"]["poetry"]["version"]
    except Exception:
        APP_VERSION = "unknown"
