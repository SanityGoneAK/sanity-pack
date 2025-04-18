# by https://github.com/isHarryh
import importlib
import pkgutil
import types

def get_modules_from_package(package: types.ModuleType):
    walk_result = pkgutil.walk_packages(package.__path__, package.__name__ + ".")
    module_names = [name for _, name, is_pkg in walk_result if not is_pkg]
    return [importlib.import_module(name) for name in module_names]


def get_modules_from_package_name(package_name: str):
    package = importlib.import_module(package_name)
    return get_modules_from_package(package)