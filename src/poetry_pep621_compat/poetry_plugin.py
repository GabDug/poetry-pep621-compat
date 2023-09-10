from __future__ import annotations
import functools
import operator

from pathlib import Path
import pprint
import re
from typing import TYPE_CHECKING, Any, Iterable

from poetry.toml import TOMLFile
from poetry.console.application import Application
from poetry.plugins.application_plugin import ApplicationPlugin

# Import PyProjectTOML
import poetry.core.pyproject.toml as poetry_toml

from packaging.requirements import Requirement
import tomlkit
from tomlkit.toml_document import TOMLDocument

if TYPE_CHECKING:
    from collections.abc import Sequence


def poetry_config_patched(self: poetry_toml.PyProjectTOML) -> dict[str, Any]:
    # return self._data["tool"]["poetry"]
    print("poetry_config_patched")
    # breakpoint()
    if len(self.data) == 0:
        # raise RuntimeError("self.data is empty")
        from tomlkit.toml_file import TOMLFile as BaseTOMLFile

        data = BaseTOMLFile.read(self)
    else:
        data = self.data
    try:
        tool = data["tool"]
        assert isinstance(tool, dict)
        config = tool["poetry"]
        assert isinstance(config, dict)
        return config
    except KeyError as e:
        # Check if we have valid PEP621
        project = data.get(
            "project",
        )
        if not project:
            from poetry.core.pyproject.exceptions import PyProjectException

            # breakpoint()
            raise PyProjectException(
                f"[tool.poetry] section not found in {self._path.as_posix()}"
            ) from e

        print("[EXPERIMENTAL] Enabling PEP621 compatibility mode")

        poetry_toml = convert_pep621_to_poetry_config(data)

        #    XXX map dev-dependencies and groups
        pprint.pprint(poetry_toml)
        print("poetry_toml")
        print(poetry_toml)
        return_data = poetry_toml["tool"]["poetry"]
        assert isinstance(return_data, dict)

        return poetry_toml["tool"]["poetry"]


def convert_pep621_to_poetry_config(data):
    # print("convert_pep621_to_poetry_config")
    # print(data)
    project = data.get("project", {})
    poetry_toml = {
        "name": project.get("name", ""),
        "version": project.get("version", "0.0.0"),
        "description": project.get("description", ""),
        "authors": project.get("authors", []),
    }
    # Authors are string only with Poetry

    poetry_toml["authors"] = _convert_authors_maintainers(project.get("authors"))
    poetry_toml["maintainers"] = _convert_authors_maintainers(
        project.get("maintainers", [])
    )
    if project.get("license"):
        pep_license = project.get("license")
        if isinstance(pep_license, str):
            poetry_toml["license"] = pep_license
        elif isinstance(pep_license, dict):
            poetry_toml["license"] = pep_license.get("text", pep_license.get("file"))

    if project.get("keywords"):
        poetry_toml["keywords"] = project.get("keywords")

    if project.get("classifiers"):
        poetry_toml["classifiers"] = project.get("classifiers")
    if project.get("readme"):
        project_readme = project.get("readme")
        poetry_toml["readme"] = (
            project_readme
            if isinstance(project_readme, str)
            else project_readme["file"]
        )

    if project.get("urls"):
        project_urls = project.get("urls")
        # Make project_urls lowercase
        original_case = {k.lower(): k for k, v in project_urls.items()}
        project_urls = {k.lower(): v for k, v in project_urls.items()}
        for specific in ["homepage", "documentation", "repository"]:
            # Lets be case-insensitive
            if specific in project_urls:
                poetry_toml[specific] = project_urls[specific]
                del project_urls[specific]
            # Other urls go in poetry_toml_urls
        poetry_toml["urls"] = {original_case[k]: v for k, v in project_urls.items()}

    if project.get("scripts"):
        poetry_toml["scripts"] = project.get("scripts")

    if project.get("entry-points"):
        poetry_plugin = project.get("entry-points").get("poetry.application.plugin")
        if poetry_plugin:
            poetry_toml["plugins"] = {}
            poetry_toml["plugins"]["poetry.application.plugin"] = poetry_plugin

    poetry_toml["dependencies"] = {}
    if project.get("requires-python"):
        # XXX We might need to parse the version
        poetry_toml["dependencies"]["python"] = project.get("requires-python")
        # Append <4.0.0 because it's expected by poetry
        poetry_toml["dependencies"]["python"] = (
            poetry_toml["dependencies"]["python"] + ",<4.0.0"
        )
    if project.get("dependencies"):
        deps_list: list[str] = project.get("dependencies")
        target_deps: dict[str, Any] = poetry_toml["dependencies"]
        extract_deps(deps_list, target_deps)

        # Create [tool.poetry.group.dev.dependencies]
    if not poetry_toml.get("group"):
        poetry_toml["group"] = {}
    if not poetry_toml["group"].get("dev"):
        poetry_toml["group"]["dev"] = {}
    poetry_toml["group"]["dev"]["dependencies"] = {}

    # XXX Try optional-dependencies
    # Try PDM dev-dependencies
    if pdm_dev_deps := data.get("tool", {}).get("pdm", {}).get("dev-dependencies", {}):
        if "dev" in pdm_dev_deps:
            deps_list: list[str] = pdm_dev_deps["dev"]
            target_deps: dict[str, Any] = poetry_toml["group"]["dev"]["dependencies"]
            extract_deps(deps_list, target_deps)
    x = {}
    x["tool"] = {}
    x["tool"]["poetry"] = poetry_toml
    return x


def extract_deps(deps_list: list[str], target_deps: dict[str, Any]):
    # Map from a list to a dict
    for dep in deps_list:
        package_name, target_dep = parse_pep508_to_poetry(dep)
        target_deps[package_name] = target_dep


def parse_pep508_to_poetry(dep: str) -> tuple[str, dict[str, Any] | str]:
    assert isinstance(dep, str)
    # 1. Parse dep string PEP508
    req = Requirement(dep)
    target_dep: dict[str, Any] | str = {}
    # breakpoint()
    if not req.marker and not req.extras and str(req.specifier) != "":
        target_dep = str(req.specifier)
    elif req.url and req.url.startswith("git+"):
        # XXX We need to differenciate between tag and ref (poetry does not seem to mind nevertheless)
        # XXX support subdirectory
        # XXX Support egg
        url = req.url[4:]
        url_no_rev = url.split("@")[0]
        rev = url.split("@")[1]
        target_dep = {}
        target_dep["git"] = url_no_rev
        target_dep["rev"] = rev

    else:
        target_dep = {}
        target_dep["version"] = str(req.specifier)
        if req.marker:
            target_dep["markers"] = str(req.marker)
        if req.extras:
            target_dep["extras"] = list(req.extras)
    if isinstance(target_dep, dict):
        if "version" in target_dep and len(target_dep) == 1:
            if target_dep["version"] == "":
                target_dep = "*"
    return req.name, target_dep


def _convert_authors_maintainers(authors: Sequence[str]) -> list[dict[str, str]]:
    new_authors = []
    for i, author in enumerate(authors):
        if isinstance(author, dict):
            new_authors.append(
                author["name"] + (" <" + author["email"] + ">")
                if "email" in author
                else ""
            )
    return new_authors


class FakeTOMLFile(TOMLFile):
    def __init__(self, path: Path, toml_document) -> None:
        super().__init__(path)
        self._path = path
        self._toml_document: TOMLDocument | None = toml_document

    def read(self):
        # print("FakeTOMLFile.read")
        # super().read()
        return self._toml_document

    def read_original(self):
        return BaseTOMLFile(self.path).read()

    def write(self, data: TOMLDocument) -> None:
        diff = compare_dicts(self.read(), data)
        original = self.read_original()
        breakpoint()
        for k, v in diff.items():
            if k[0] == "tool" and k[1] == "poetry":
                if k[2] == "dependencies":
                    dep_name = k[3]
                    if dep_name == "python":
                        # XXX Support this?
                        continue

                    if v[0] == "added":
                        original["project"]["dependencies"].append(
                            f"{dep_name}{str(_convert_specifier(v[1]))}"
                        )
                    elif v[0] == "modified":
                        # Get the item index
                        for i, item in enumerate(original["project"]["dependencies"]):
                            if item.startswith(dep_name):
                                # XXX Do not use startswith, use Requirement
                                original["project"]["dependencies"][
                                    i
                                ] = f"{dep_name}{str(_convert_specifier(v[1][1]))}"
                                break
                    elif v[0] == "deleted":
                        for i, item in enumerate(original["project"]["dependencies"]):
                            if item.startswith(dep_name):
                                del original["project"]["dependencies"][i]
                                break
                if k[2] == "version":
                    # IF not dynamic
                    if "version" not in original["project"].get("dynamic", []):
                        original["project"]["version"] = v[1][1]
        # XXX Compare and save the difference
        breakpoint()
        return super().write(original)
        # raise RuntimeError("FakeTOMLFile.write")
        # return super().write(data)


def file_patched(self: poetry_toml.PyProjectTOML) -> TOMLFile:
    # print("file_patched")
    # breakpoint()
    # raise RuntimeError("file_patched")
    # breakpoint()
    real_file = self._toml_file
    from tomlkit.toml_file import TOMLFile as BaseTOMLFile

    # return real_file
    data = BaseTOMLFile(self._toml_file.path).read()

    # data = self._toml_file.read()
    # if not data or len(data) == 0:
    #     # breakpoint()
    # return real_file
    # return FakeTOMLFile(self._path, data)
    if data.get("tool", {}).get("poetry"):
        return real_file
    else:
        # def read_patched() -> TOMLDocument:
        #     # Create a TOMLDocument from poetry_tml
        #     data = convert_pep621_to_poetry_config(self, self.data.get("project", {}))
        #     merged_data = {**data, **self.data}
        #     return TOMLDocument(merged_data)
        # real_file.read = read_patched

        data = convert_pep621_to_poetry_config(data)
        # breakpoint()
        return FakeTOMLFile(self._path, FakeTomlDocument(data))
    # class PatchedTOMLFile(TOMLFile):
    #     def read(self) -> TOMLDocument:
    #         # Create a TOMLDocument from poetry_tml
    #         return TOMLDocument(self.poetry_config)


import poetry.pyproject.toml as poetry_toml_not_core


class FakeTomlDocument(TOMLDocument):
    def __init__(self, data: dict) -> None:
        super().__init__()
        # We have a nested dict, with arrays dict and string
        # Add to the data
        for k, v in data.items():
            if isinstance(v, dict):
                self[k] = tomlkit.table()
                for k2, v2 in v.items():
                    self[k][k2] = v2
            elif isinstance(v, list):
                self[k] = []
                for v2 in v:
                    self[k].append(v2)
            else:
                self[k] = v


def patched_data(self: poetry_toml.PyProjectTOML) -> TOMLDocument:
    if self._toml_document is None:
        if not self.file.exists():
            self._toml_document = TOMLDocument()
        else:
            self._toml_document = self.file.read()
    # breakpoint()
    if self._toml_document and not self._toml_document.get("tool", {}).get("poetry"):
        # Create a TOMLDocument from poetry_tml
        # breakpoint()
        data = convert_pep621_to_poetry_config(dict(self._toml_document))

        merged_data = {**data, **self._toml_document}
        self._toml_document = TOMLDocument(merged_data)
    # breakpoint()
    return self._toml_document


class PatchedPyProjectTOML(poetry_toml_not_core.PyProjectTOML):
    poetry_config = property(poetry_config_patched)
    file = property(file_patched)
    data = property(patched_data)


def patched_poetry__init__(
    self, file: Path, local_config, package, pyproject_type=PatchedPyProjectTOML
):
    self._pyproject = PatchedPyProjectTOML(file)
    self._package = package
    self._local_config = local_config
    # breakpoint()


from tomlkit.toml_file import TOMLFile as BaseTOMLFile


def patched_tomlfile_read(self: TOMLFile) -> TOMLDocument:
    x = BaseTOMLFile.read(self)
    # breakpoint()
    if str(self._path).endswith("pyproject.toml") and x.get("project"):
        poetry_config = convert_pep621_to_poetry_config(x)
        x = {
            **x,
            **poetry_config,
        }
    return TOMLDocument(x)


class PoetryPEP621CompatPlugin(ApplicationPlugin):
    application: Application | None

    def activate(self, application: Application) -> None:
        # print("PoetryPEP621CompatPlugin.activate")
        self.application = application
        self._patch_poetry()

    def _patch_poetry(self):
        from poetry.core import poetry

        poetry.PyProjectTOML = PatchedPyProjectTOML
        # poetry.Poetry.pyproject = property(lambda self: PatchedPyProjectTOML(self.file))
        poetry.Poetry.__init__ = patched_poetry__init__
        # Poetry config used for read

        poetry_toml.PyProjectTOML.poetry_config = property(poetry_config_patched)
        # File used for write
        poetry_toml.PyProjectTOML.file = property(file_patched)
        TOMLFile.read = patched_tomlfile_read
        # Mokey patch the property on PyProjectTOML

    # def _handle_post_command(
    #     self, event: ConsoleTerminateEvent | Event, event_name: str, dispatcher: EventDispatcher
    # ) -> None:
    #     assert isinstance(event, ConsoleTerminateEvent)
    #     if event.exit_code != 0:
    #         # The command failed, so the plugin shouldn't do anything
    #         return

    #     command = event.command
    #     printer = PoetryPrinter(event.io)
    #     try:
    #         dry_run: bool = bool(command.option("dry-run"))
    #     except CleoValueError:
    #         dry_run = False

    #     if isinstance(command, SelfCommand):
    #         printer.debug("Poetry pre-commit plugin does not run for 'self' command.")
    #         return

    #     if any(isinstance(command, t) for t in [InstallCommand, AddCommand]):
    #         PoetrySetupPreCommitHooks(printer, dry_run=dry_run).execute()

    #     if any(isinstance(command, t) for t in [InstallCommand, AddCommand, LockCommand, UpdateCommand]):
    #         if self.application is None:
    #             msg = "self.application is None"
    #             raise RuntimeError(msg)

    #         # Get all locked dependencies from self.application
    #         run_sync_pre_commit_version(printer, dry_run, self.application)


# class SyncPreCommitPoetryCommand(Command):
#     name = "sync-pre-commit"
#     description = "Sync `.pre-commit-config.yaml` hooks versions with the lockfile"
#     help = "Sync `.pre-commit-config.yaml` hooks versions with the lockfile"
#     options = [
#         option(
#             "dry-run",
#             None,
#             "Output the operations but do not update the pre-commit file.",
#         ),
#     ]

#     def handle(self) -> int:
#         # XXX(dugab): handle return codes
#         if not self.application:
#             msg = "self.application is None"
#             raise RuntimeError(msg)
#         assert isinstance(self.application, Application)
#         run_sync_pre_commit_version(PoetryPrinter(self.io, with_prefix=False), False, self.application)
#         return 0


# def sync_pre_commit_poetry_command_factory() -> SyncPreCommitPoetryCommand:
#     return SyncPreCommitPoetryCommand()


def compare_dicts_new(a, b):
    """Return the nested diff between two dicts, in three groups: addition, deletetion, modifications"""
    diff = {}
    a_keys = set(a.keys())
    b_keys = set(b.keys())
    for k in a_keys - b_keys:
        diff[k] = a[k]
    for k in b_keys - a_keys:
        diff[k] = b[k]
    for k in a_keys & b_keys:
        if isinstance(a[k], dict) and isinstance(b[k], dict):
            nested_diff = compare_dicts(a[k], b[k])
            if nested_diff:
                diff[k] = nested_diff
        elif a[k] != b[k]:
            diff[k] = b[k]
    return diff


def compare_dicts(dict1, dict2):
    """
    Compare two dictionaries and return the differences between them.

    Args:
    - dict1: The first dictionary to compare.
    - dict2: The second dictionary to compare.

    Returns:
    - A dictionary containing the differences between dict1 and dict2.
      Keys are the paths to modified elements, and values are tuples with
      the type of change ('added', 'deleted', 'modified') and the values
      from dict1 and dict2.
    """
    diff = {}

    def compare_recursive(path, d1, d2):
        for key in set(d1.keys()) | set(d2.keys()):
            new_path = path + [key]

            if key not in d1:
                diff[tuple(new_path)] = ("added", d2[key])
            elif key not in d2:
                diff[tuple(new_path)] = ("deleted", d1[key])
            elif isinstance(d1[key], dict) and isinstance(d2[key], dict):
                compare_recursive(new_path, d1[key], d2[key])
            elif d1[key] != d2[key]:
                diff[tuple(new_path)] = ("modified", (d1[key], d2[key]))

    compare_recursive([], dict1, dict2)
    return diff


# Example usage:
dict1 = {
    "a": 1,
    "b": {
        "c": "x",
        "d": [1, 2, 3],
    },
    "e": "hello",
}

dict2 = {
    "a": 1,
    "b": {
        "c": "y",
        "d": [1, 2, 4],
    },
    "f": "world",
}

# differences = compare_dicts(dict1, dict2)
# for key, (change, values) in differences.items():
#     print(f"{key}: {change} ({values[0]} -> {values[1]})")
from packaging.markers import Marker


# FROM PDM
def _convert_req(name: str, req_dict: Any | list[Any]) -> Iterable[str]:
    if isinstance(req_dict, list):
        for req in req_dict:
            yield from _convert_req(name, req)
    elif isinstance(req_dict, str):
        pass
        # yield Requirement.from_req_dict(name, _convert_specifier(req_dict)).as_line()
    else:
        assert isinstance(req_dict, dict)
        req_dict = dict(req_dict)
        req_dict.pop("optional", None)  # Ignore the 'optional' key
        if "version" in req_dict:
            req_dict["version"] = _convert_specifier(str(req_dict["version"]))
        markers: list[Marker] = []
        if "markers" in req_dict:
            markers.append(Marker(req_dict.pop("markers")))  # type: ignore[arg-type]
        if "python" in req_dict:
            markers.append(
                Marker(_convert_python(str(req_dict.pop("python"))).as_marker_string())
            )
        if markers:
            req_dict["marker"] = str(functools.reduce(operator.and_, markers)).replace(
                '"', "'"
            )
        if "rev" in req_dict or "branch" in req_dict or "tag" in req_dict:
            req_dict["ref"] = req_dict.pop(
                "rev", req_dict.pop("tag", req_dict.pop("branch", None))  # type: ignore[arg-type]
            )
        yield Requirement.from_req_dict(name, req_dict).as_line()


VERSION_RE = re.compile(r"([^\d\s]*)\s*(\d.*?)\s*(?=,|$)")
from packaging.specifiers import SpecifierSet


def _convert_python(python: str) -> SpecifierSet:
    if not python:
        return SpecifierSet()
    parts = [SpecifierSet(_convert_specifier(s)) for s in python.split("||")]
    return functools.reduce(operator.or_, parts)


def _convert_specifier(version: str) -> str:
    parts = []
    for op, ver in VERSION_RE.findall(str(version)):
        if op == "~":
            op += "="
        elif op == "^":
            major, *vparts = ver.split(".")
            next_major = ".".join([str(int(major) + 1)] + ["0"] * len(vparts))
            parts.append(f">={ver},<{next_major}")
            continue
        elif not op:
            op = "=="
        parts.append(f"{op}{ver}")
    return ",".join(parts)
