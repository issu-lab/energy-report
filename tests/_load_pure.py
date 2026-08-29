"""Load dependency-light modules without Home Assistant installed."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "custom_components" / "energy_report"
PACKAGE = "energy_report_pure"


class _Platform:
    SENSOR = "sensor"
    NUMBER = "number"
    BUTTON = "button"


homeassistant = sys.modules.setdefault("homeassistant", ModuleType("homeassistant"))
ha_const = sys.modules.setdefault("homeassistant.const", ModuleType("homeassistant.const"))
ha_const.Platform = _Platform
homeassistant.const = ha_const


def _load(name: str):
    package = sys.modules.setdefault(PACKAGE, ModuleType(PACKAGE))
    package.__path__ = [str(SOURCE)]
    full_name = f"{PACKAGE}.{name}"
    if full_name in sys.modules:
        return sys.modules[full_name]
    spec = spec_from_file_location(full_name, SOURCE / f"{name}.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {name}")
    module = module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


const = _load("const")
models = _load("models")
source = _load("source")
report = _load("report")
archive = _load("archive")

