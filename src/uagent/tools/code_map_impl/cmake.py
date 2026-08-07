"""Conservative CMake condition and variable evaluation."""
from __future__ import annotations
import re

def _cmake_eval_condition(condition: str, variables: dict[str, str]) -> bool:
    condition=re.sub(r"\$\{([^}]+)\}",lambda m:variables.get(m.group(1),""),condition).strip()
    tokens=re.findall(r"\(|\)|AND|OR|NOT|[^\s()]+",condition,re.I)
    def atom(i):
        if i<len(tokens) and tokens[i].upper()=="NOT":
            value,j=atom(i+1); return (not value,j)
        if i<len(tokens) and tokens[i]=="(":
            value,j=expr(i+1)
            return (value,j+1 if j<len(tokens) and tokens[j]==")" else j)
        token=tokens[i] if i<len(tokens) else ""
        value=variables.get(token, token if token.lower() in ("on","true","yes","y") else "")
        return (str(value).lower() not in ("","0","false","off","no","n","notfound"),i+1)
    def expr(i):
        left,i=atom(i)
        while i<len(tokens) and tokens[i] != ")":
            op=tokens[i].upper()
            if op not in ("AND","OR"): break
            right,i=atom(i+1); left=(left and right) if op=="AND" else (left or right)
        return left,i
    try: return bool(expr(0)[0])
    except Exception: return False


def cmake_active_source(text: str) -> str:
    """Conservatively evaluate literal CMake set/if/elseif/else blocks."""
    variables={}; output=[]; active=[True]; branch_taken=[False]
    for raw in text.splitlines():
        line=raw.strip()
        m=re.match(r"set\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s+([^)]*)\)",line,re.I)
        if m and active[-1]: variables[m.group(1)]=m.group(2).strip().strip('"'); continue
        m=re.match(r"if\s*\(\s*([^)]*)\)",line,re.I)
        if m:
            truth=_cmake_eval_condition(m.group(1),variables); active.append(active[-1] and truth); branch_taken.append(truth); continue
        m=re.match(r"elseif\s*\(\s*([^)]*)\)",line,re.I)
        if m and len(active)>1:
            truth=_cmake_eval_condition(m.group(1),variables); active[-1]=active[-2] and (not branch_taken[-1]) and truth; branch_taken[-1]=branch_taken[-1] or truth; continue
        if re.match(r"else\s*\(",line,re.I):
            if len(active)>1: active[-1]=active[-2] and not branch_taken[-1]; branch_taken[-1]=True
            continue
        if re.match(r"endif\s*\(",line,re.I):
            if len(active)>1: active.pop(); branch_taken.pop()
            continue
        if active[-1]:
            expanded=re.sub(r"\$\{([^}]+)\}",lambda m:variables.get(m.group(1),m.group(0)),raw)
            expanded=re.sub(r"\$<[^>]*>","",expanded)
            output.append(expanded)
    return "\n".join(output)


