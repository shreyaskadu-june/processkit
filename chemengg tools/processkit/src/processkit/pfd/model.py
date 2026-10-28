"""Flowsheet specification and Graphviz DOT generation for process flow diagrams.

Equipment is identified by ``id`` (e.g. "P-101") and drawn with a shape chosen
from its ``kind``. Streams are directed edges between equipment ids, with an
optional label such as a stream name and flow rate.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import yaml

#: Graphviz node attributes per equipment kind.
KIND_STYLES: dict[str, dict[str, str]] = {
    "tank": {"shape": "cylinder", "style": "filled", "fillcolor": "#e8f1fb"},
    "vessel": {"shape": "box", "style": "rounded,filled", "fillcolor": "#eef7ee"},
    "column": {"shape": "box", "style": "rounded,filled", "fillcolor": "#fdf3e1"},
    "reactor": {"shape": "box", "style": "rounded,filled", "fillcolor": "#fbe9e9"},
    "heat_exchanger": {"shape": "box", "style": "rounded,filled", "fillcolor": "#f3ecfb"},
    "pump": {"shape": "circle", "style": "filled", "fillcolor": "#ffffff", "label_default": "P"},
    "compressor": {"shape": "trapezium", "style": "filled", "fillcolor": "#ffffff", "label_default": "C"},
    "valve": {"shape": "diamond", "style": "filled", "fillcolor": "#ffffff", "label_default": "V"},
    "source": {"shape": "plaintext"},
    "sink": {"shape": "plaintext"},
}
DEFAULT_STYLE = {"shape": "box", "style": "filled", "fillcolor": "#ffffff"}


@dataclass(frozen=True)
class Unit:
    id: str
    kind: str = "vessel"
    label: str | None = None  #: display text; defaults to the id
    attrs: Mapping[str, str] = field(default_factory=dict)  #: extra Graphviz attributes


@dataclass(frozen=True)
class Stream:
    source: str
    target: str
    label: str | None = None
    attrs: Mapping[str, str] = field(default_factory=dict)


@dataclass
class Flowsheet:
    title: str = "Process flow diagram"
    units: list[Unit] = field(default_factory=list)
    streams: list[Stream] = field(default_factory=list)
    rankdir: str = "LR"

    # ---- construction ------------------------------------------------------
    def add_unit(self, id: str, kind: str = "vessel", label: str | None = None, **attrs: str) -> "Flowsheet":
        self.units.append(Unit(id, kind, label, attrs))
        return self

    def connect(self, source: str, target: str, label: str | None = None, **attrs: str) -> "Flowsheet":
        self.streams.append(Stream(source, target, label, attrs))
        return self

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Flowsheet":
        units = [
            Unit(
                id=str(u["id"]),
                kind=str(u.get("kind", "vessel")),
                label=u.get("label"),
                attrs={k: str(v) for k, v in u.get("attrs", {}).items()},
            )
            for u in data.get("units", [])
        ]
        streams = [
            Stream(
                source=str(s["from"]),
                target=str(s["to"]),
                label=s.get("label"),
                attrs={k: str(v) for k, v in s.get("attrs", {}).items()},
            )
            for s in data.get("streams", [])
        ]
        fs = cls(title=str(data.get("title", "Process flow diagram")), units=units, streams=streams,
                 rankdir=str(data.get("rankdir", "LR")))
        fs.validate()
        return fs

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Flowsheet":
        with open(path, encoding="utf-8") as fh:
            return cls.from_dict(yaml.safe_load(fh) or {})

    def validate(self) -> None:
        ids = [u.id for u in self.units]
        if len(ids) != len(set(ids)):
            dupes = sorted({i for i in ids if ids.count(i) > 1})
            raise ValueError(f"Duplicate unit ids: {dupes}")
        known = set(ids)
        for s in self.streams:
            for end in (s.source, s.target):
                if end not in known:
                    raise ValueError(f"Stream references unknown unit '{end}'. Known ids: {sorted(known)}")
        for u in self.units:
            if u.kind not in KIND_STYLES:
                raise ValueError(f"Unknown kind '{u.kind}' for '{u.id}'. Known kinds: {sorted(KIND_STYLES)}")

    # ---- output ------------------------------------------------------------
    @staticmethod
    def _q(text: str) -> str:
        """Quote a DOT string, escaping backslashes and quotes and turning newlines into DOT line breaks."""
        escaped = str(text).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return '"' + escaped + '"'

    def to_dot(self) -> str:
        self.validate()
        lines = [
            "digraph flowsheet {",
            f"  graph [rankdir={self.rankdir}, label={self._q(self.title)}, labelloc=t, fontname=\"Helvetica\", pad=0.3];",
            "  node [fontname=\"Helvetica\", fontsize=11, margin=\"0.15,0.08\"];",
            "  edge [fontname=\"Helvetica\", fontsize=9, color=\"#444444\", arrowsize=0.7];",
        ]
        for u in self.units:
            style = dict(KIND_STYLES[u.kind])
            label_default = style.pop("label_default", None)
            label = u.label or label_default or u.id
            if u.label is None and label_default:
                label = f"{label_default}\n{u.id}"
            style.update(u.attrs)
            attr_text = ", ".join(f"{k}={self._q(v)}" for k, v in style.items())
            lines.append(f"  {self._q(u.id)} [label={self._q(label)}, {attr_text}];")
        for s in self.streams:
            attrs = {"label": s.label} if s.label else {}
            attrs.update(s.attrs)
            attr_text = ", ".join(f"{k}={self._q(v)}" for k, v in attrs.items())
            suffix = f" [{attr_text}]" if attr_text else ""
            lines.append(f"  {self._q(s.source)} -> {self._q(s.target)}{suffix};")
        lines.append("}")
        return "\n".join(lines) + "\n"


def dot_available() -> bool:
    return shutil.which("dot") is not None


def render(flowsheet: Flowsheet, output: str | Path, fmt: str | None = None) -> Path:
    """Render with the Graphviz ``dot`` executable. Format is taken from the file extension if not given."""
    output = Path(output)
    fmt = fmt or output.suffix.lstrip(".") or "svg"
    if not dot_available():
        raise RuntimeError(
            "Graphviz 'dot' was not found on PATH. Install Graphviz (apt install graphviz, "
            "brew install graphviz, or conda install graphviz), or write the DOT text with to_dot() "
            "and render it elsewhere."
        )
    proc = subprocess.run(
        ["dot", f"-T{fmt}", "-o", str(output)],
        input=flowsheet.to_dot(),
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Graphviz failed: {proc.stderr.strip()}")
    return output
