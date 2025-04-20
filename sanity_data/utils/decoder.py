# by https://github.com/isHarryh
import importlib
import pkgutil
import types

def get_modules_from_package(package: types.ModuleType) -> dict[str, types.ModuleType]:
    walk_result = pkgutil.walk_packages(package.__path__, package.__name__ + ".")
    modules = {}

    for _, name, is_pkg in walk_result:
        if not is_pkg:
            short_name = name.split(".")[-1]  # get just the module name, not full path
            modules[short_name] = importlib.import_module(name)

    return modules


def get_modules_from_package_name(package_name: str):
    package = importlib.import_module(package_name)
    return get_modules_from_package(package)


