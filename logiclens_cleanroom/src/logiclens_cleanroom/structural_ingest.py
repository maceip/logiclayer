from __future__ import annotations

import hashlib
import re
from collections import deque
from pathlib import Path
from typing import Iterable

from tree_sitter import Node
from tree_sitter_language_pack import get_parser

from logiclens_cleanroom.models import EdgeKind, GraphEdge, GraphNode, KnowledgeGraph, NodeKind, SourceRange

SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        "dist",
        "build",
        ".next",
        "target",
    }
)

EXT_TO_LANG = {
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".py": "python",
    ".go": "go",
    ".java": "java",
}


def _walk_ts(n: Node) -> list[Node]:
    out: list[Node] = []
    stack = [n]
    while stack:
        cur = stack.pop()
        out.append(cur)
        stack.extend(reversed(cur.children))
    return out


def _name_from(node: Node, field: str = "name") -> str:
    n = node.child_by_field_name(field)
    if n and n.text:
        return n.text.decode("utf-8", errors="ignore")
    return "anonymous"


def _range(n: Node) -> SourceRange:
    return SourceRange(
        start_line=n.start_point[0] + 1,
        start_col=n.start_point[1],
        end_line=n.end_point[0] + 1,
        end_col=n.end_point[1],
    )


def _posix(rel: Path) -> str:
    return rel.as_posix()


def _file_id(repo: str, rel: str) -> str:
    return f"file:{repo}:{rel}"


def _code_id(repo: str, rel: str, line: int, name: str) -> str:
    h = hashlib.sha256(f"{repo}:{rel}:{line}:{name}".encode()).hexdigest()[:12]
    return f"code:{repo}:{h}"


def _edge_id(a: str, b: str, t: str) -> str:
    return hashlib.sha256(f"{a}|{b}|{t}".encode()).hexdigest()[:16]


def _decode_import_string(n: Node) -> str:
    raw = n.text or b""
    s = raw.decode("utf-8", errors="ignore").strip()
    if len(s) >= 2 and s[0] in "'\"`" and s[-1] == s[0]:
        s = s[1:-1]
    return s


def _ts_import_spec(root: Node) -> str | None:
    strings: list[str] = []
    has_from = b"from" in (root.text or b"")
    for t in _walk_ts(root):
        if t.type in {"string", "string_fragment", "string_literal"}:
            d = _decode_import_string(t)
            if d:
                strings.append(d)
    if not strings:
        return None
    if has_from:
        return strings[-1]
    return strings[0]


def _resolve_local_import(importer_rel: str, spec: str, files: set[str]) -> str | None:
    if not spec.startswith("."):
        return None
    base = Path(importer_rel).parent
    target = (base / spec).as_posix()
    candidates = [
        target,
        target + ".ts",
        target + ".tsx",
        target + ".js",
        target + ".jsx",
        target + ".py",
    ]
    for c in candidates:
        if c in files:
            return c
    # index files
    for ext in (".ts", ".tsx", ".js"):
        idx = f"{target}/index{ext}"
        if idx in files:
            return idx
    return None


def extract_code_units(
    lang: str,
    rel_path: str,
    root: Node,
    repo_name: str,
    language_label: str,
) -> list[GraphNode]:
    units: list[GraphNode] = []
    for n in _walk_ts(root):
        kind = None
        name = "anonymous"
        if lang in {"typescript", "tsx", "javascript"}:
            if n.type == "function_declaration":
                kind = "function"
                name = _name_from(n)
            elif n.type == "class_declaration":
                kind = "class"
                name = _name_from(n)
            elif n.type == "method_definition":
                kind = "method"
                name = _name_from(n, "name")
            elif n.type == "interface_declaration":
                kind = "interface"
                name = _name_from(n)
        elif lang == "python":
            if n.type == "function_definition":
                kind = "function"
                name = _name_from(n)
            elif n.type == "class_definition":
                kind = "class"
                name = _name_from(n)
        elif lang == "go":
            if n.type == "function_declaration":
                kind = "function"
                name = _name_from(n)
            elif n.type == "method_declaration":
                kind = "method"
                name = _name_from(n, "name")
        elif lang == "java":
            if n.type == "method_declaration":
                kind = "method"
                name = _name_from(n, "name")
            elif n.type == "class_declaration":
                kind = "class"
                name = _name_from(n)

        if not kind:
            continue
        text = (n.text or b"").decode("utf-8", errors="ignore")
        if len(text) > 12000:
            text = text[:12000] + "\n/* truncated */"
        line = n.start_point[0] + 1
        cid = _code_id(repo_name, rel_path, line, name)
        fqn = f"{repo_name}/{rel_path}#{name}"
        units.append(
            GraphNode(
                node_id=cid,
                kind=NodeKind.CODE,
                name=name,
                repo_name=repo_name,
                language=language_label,
                file_path=rel_path,
                fqn=fqn,
                range=_range(n),
                content=text,
            )
        )
    return units


def extract_file_import_edges(
    repo_name: str,
    rel_path: str,
    root: Node,
    existing_files: set[str],
) -> list[tuple[str, str]]:
    """Return (source_file_id, target_file_rel) for resolved local imports."""
    out: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for n in _walk_ts(root):
        if n.type not in {"import_statement", "export_statement"}:
            continue
        if n.type == "export_statement" and b"from" not in (n.text or b""):
            continue
        spec = _ts_import_spec(n)
        if not spec or spec.startswith("type "):
            continue
        if spec.startswith("type "):
            spec = spec[5:].strip()
        resolved = _resolve_local_import(rel_path, spec, existing_files)
        if resolved:
            pair = (rel_path, resolved)
            if pair not in seen:
                seen.add(pair)
                out.append(pair)
    return out


def iter_source_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in p.parts):
            continue
        if p.suffix.lower() in EXT_TO_LANG:
            yield p


def build_structural_graph(repo_root: Path, repo_name: str | None = None) -> KnowledgeGraph:
    """Paper §3.1 structural phase: System, Project, File, Code nodes and CONTAINS / DEPENDS_ON."""
    root = repo_root.resolve()
    name = repo_name or root.name
    system_id = "system:default"
    project_id = f"project:{name}"

    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []

    nodes[system_id] = GraphNode(node_id=system_id, kind=NodeKind.SYSTEM, name=name, repo_name=name)
    nodes[project_id] = GraphNode(
        node_id=project_id,
        kind=NodeKind.PROJECT,
        name=name,
        repo_name=name,
    )
    edges.append(
        GraphEdge(edge_id=_edge_id(system_id, project_id, "CONTAINS"), source_id=system_id, target_id=project_id, edge_type=EdgeKind.CONTAINS)
    )

    rel_files: list[tuple[str, str, Node, str]] = []
    file_set: set[str] = set()

    for path in iter_source_files(root):
        rel = _posix(path.relative_to(root))
        lang = EXT_TO_LANG.get(path.suffix.lower())
        if not lang:
            continue
        try:
            parser = get_parser(lang)
        except Exception:
            continue
        src = path.read_bytes()
        tree = parser.parse(src)
        rel_files.append((rel, lang, tree.root_node, path.suffix.lower()))
        file_set.add(rel)

    # Register all file nodes first so import resolution can link before parse order
    for rel, lang, _root_node, _ext in rel_files:
        fid = _file_id(name, rel)
        if fid not in nodes:
            nodes[fid] = GraphNode(
                node_id=fid,
                kind=NodeKind.FILE,
                name=Path(rel).name,
                repo_name=name,
                language=lang,
                file_path=rel,
            )
            edges.append(
                GraphEdge(
                    edge_id=_edge_id(project_id, fid, "CONTAINS"),
                    source_id=project_id,
                    target_id=fid,
                    edge_type=EdgeKind.CONTAINS,
                )
            )

    # Code units + import edges
    for rel, lang, root_node, _ext in rel_files:
        fid = _file_id(name, rel)

        try:
            units = extract_code_units(lang, rel, root_node, name, lang)
        except Exception:
            units = []
        for u in units:
            nodes[u.node_id] = u
            edges.append(
                GraphEdge(
                    edge_id=_edge_id(fid, u.node_id, "CONTAINS"),
                    source_id=fid,
                    target_id=u.node_id,
                    edge_type=EdgeKind.CONTAINS,
                )
            )

        if lang in {"typescript", "tsx", "javascript"}:
            for src_rel, tgt_rel in extract_file_import_edges(name, rel, root_node, file_set):
                sf = _file_id(name, src_rel)
                tf = _file_id(name, tgt_rel)
                eid = _edge_id(sf, tf, "DEPENDS_ON")
                if not any(e.edge_id == eid for e in edges):
                    edges.append(GraphEdge(edge_id=eid, source_id=sf, target_id=tf, edge_type=EdgeKind.DEPENDS_ON))

    kg = KnowledgeGraph(system_id=system_id, nodes=nodes, edges=edges)
    return kg


def build_multi_repo_graph(repo_roots: list[tuple[Path, str]]) -> KnowledgeGraph:
    """Merge repositories under one System node (paper multi-repository setting)."""
    if not repo_roots:
        raise ValueError("repo_roots required")
    system_id = "system:default"
    merged = KnowledgeGraph(system_id=system_id, nodes={}, edges=[])

    merged.nodes[system_id] = GraphNode(node_id=system_id, kind=NodeKind.SYSTEM, name="merged", repo_name="multi")

    for root, repo_name in repo_roots:
        part = build_structural_graph(root.resolve(), repo_name=repo_name)
        for nid, n in part.nodes.items():
            if n.kind == NodeKind.SYSTEM:
                continue
            merged.nodes[nid] = n
        for e in part.edges:
            if e.source_id == part.system_id:
                merged.edges.append(
                    GraphEdge(
                        edge_id=_edge_id(system_id, e.target_id, e.edge_type.value),
                        source_id=system_id,
                        target_id=e.target_id,
                        edge_type=e.edge_type,
                        label=e.label,
                    )
                )
            else:
                merged.edges.append(e)

    return merged


def induced_subgraph(kg: KnowledgeGraph, seed_ids: set[str], depth: int = 2) -> KnowledgeGraph:
    """BFS neighborhood for tool responses."""
    adj = kg.edge_index()
    q = deque([(nid, 0) for nid in seed_ids])
    keep = set(seed_ids)
    while q:
        nid, d = q.popleft()
        if d >= depth:
            continue
        for nb, _et, _dir in adj.get(nid, []):
            if nb not in keep:
                keep.add(nb)
                q.append((nb, d + 1))

    nodes = {k: v for k, v in kg.nodes.items() if k in keep}
    edges = [e for e in kg.edges if e.source_id in keep and e.target_id in keep]
    return KnowledgeGraph(
        system_id=kg.system_id,
        nodes=nodes,
        edges=edges,
        semantic=kg.semantic,
        entities=kg.entities,
        actions=kg.actions,
    )
