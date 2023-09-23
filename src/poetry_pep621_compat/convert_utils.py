from __future__ import annotations

import functools
import operator
import re
from typing import Any, Iterable, Sequence

from packaging.markers import Marker
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet


def _convert_authors_maintainers(authors: Sequence[dict[str, str]]) -> list[str]:
    """Convert standard authors objects to Poetry author strings"""
    poetry_authors: list[str] = []
    for i, author in enumerate(authors):
        if isinstance(author, dict):
            # We may only have email or only name from project.authors
            if len(author) == 1:
                poetry_authors.append(next(iter(author.values())))
            else:
                poetry_authors.append(f'{author["name"]}  < {author["email"]}>')
        else:
            poetry_authors.append(str(author))
    return poetry_authors


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
