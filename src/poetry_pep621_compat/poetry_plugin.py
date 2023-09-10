from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

import poetry.core.pyproject.toml as poetry_toml_core
import poetry.pyproject.toml as poetry_toml
import tomlkit
from packaging.requirements import Requirement
from poetry.console.application import Application
from poetry.plugins.application_plugin import ApplicationPlugin
from poetry.toml import TOMLFile
from tomlkit.toml_document import TOMLDocument
from tomlkit.toml_file import TOMLFile as BaseTOMLFile

from poetry_pep621_compat.convert_utils import (
    _convert_authors_maintainers,
    _convert_specifier,
)
from poetry_pep621_compat.utils import compare_dicts

if TYPE_CHECKING:
    pass


def poetry_config_patched(self: poetry_toml_core.PyProjectTOML) -> dict[str, Any]:
    if len(self.data) == 0:
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

            raise PyProjectException(
                f"[tool.poetry] section not found in {self._path.as_posix()}"
            ) from e

        print("[EXPERIMENTAL] Enabling PEP621 compatibility mode")

        poetry_toml = convert_pep621_to_poetry_config(data)

        #    XXX map dev-dependencies and groups

        return_data = poetry_toml["tool"]["poetry"]
        assert isinstance(return_data, dict)

        return poetry_toml["tool"]["poetry"]


def convert_pep621_to_poetry_config(data: MutableMapping[str, Any]) -> dict[str, Any]:
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
    return dict(tool=dict(poetry=poetry_toml))


def extract_deps(deps_list: list[str], target_deps: dict[str, Any]):
    # Map from a list to a dict
    for dep in deps_list:
        package_name, target_dep = pep508_requirement_to_poetry(dep)
        target_deps[package_name] = target_dep


def pep508_requirement_to_poetry(dep: str) -> tuple[str, dict[str, Any] | str]:
    assert isinstance(dep, str)
    # 1. Parse dep string PEP508
    req = Requirement(dep)
    target_dep: dict[str, Any] | str = {}

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


class FakeTOMLFile(TOMLFile):
    def __init__(self, path: Path, toml_document) -> None:
        super().__init__(path)
        self._path = path
        self._toml_document: TOMLDocument | None = toml_document

    def read(self):
        """Patched to read our file."""
        return self._toml_document

    def read_original(self):
        return BaseTOMLFile(self.path).read()

    def write(self, data: TOMLDocument) -> None:
        diff = compare_dicts(self.read(), data)
        original = self.read_original()

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
        # XXX Warn user that we are saving with experimental mode
        # XXX Warn if some operations could not be done
        return super().write(original)


def file_patched(self: poetry_toml_core.PyProjectTOML) -> TOMLFile:
    real_file = self._toml_file
    from tomlkit.toml_file import TOMLFile as BaseTOMLFile

    data = BaseTOMLFile(self._toml_file.path).read()

    if data.get("tool", {}).get("poetry"):
        return real_file
    else:
        data_ = convert_pep621_to_poetry_config(data)

        return FakeTOMLFile(self._path, FakeTomlDocument(data_))


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


def patched_data(self: poetry_toml_core.PyProjectTOML) -> TOMLDocument:
    if self._toml_document is None:
        if not self.file.exists():
            self._toml_document = TOMLDocument()
        else:
            self._toml_document = self.file.read()

    if self._toml_document and not self._toml_document.get("tool", {}).get("poetry"):
        # Create a TOMLDocument from poetry_tml

        data = convert_pep621_to_poetry_config(dict(self._toml_document))

        merged_data = {**data, **self._toml_document}
        self._toml_document = TOMLDocument(merged_data)

    return self._toml_document


class PatchedPyProjectTOML(poetry_toml.PyProjectTOML):
    poetry_config = property(poetry_config_patched)
    file = property(file_patched)
    data = property(patched_data)


def patched_poetry__init__(
    self, file: Path, local_config, package, pyproject_type=PatchedPyProjectTOML
):
    self._pyproject = PatchedPyProjectTOML(file)
    self._package = package
    self._local_config = local_config


def patched_tomlfile_read(self: TOMLFile) -> TOMLDocument:
    x = BaseTOMLFile.read(self)

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
        self.application = application
        self._patch_poetry()

    def _patch_poetry(self):
        from poetry.core import poetry

        # We patch the root Poetry object, so that the default PyProjectTOML class is patched
        poetry.Poetry.__init__ = patched_poetry__init__

        # Poetry config used for read
        poetry_toml_core.PyProjectTOML.poetry_config = property(poetry_config_patched)

        # File used for write
        poetry_toml_core.PyProjectTOML.file = property(file_patched)
