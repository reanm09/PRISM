import re


def zip_path_hazards(name: str) -> tuple[bool, bool]:
    normalized = name.replace("\\", "/")
    absolute = normalized.startswith("/") or re.match(r"^[A-Za-z]:/", normalized) is not None
    depth = 0
    traversal = False
    for part in normalized.split("/"):
        if part == "..":
            if depth == 0:
                traversal = True
            else:
                depth -= 1
        elif part not in ("", "."):
            depth += 1
    return traversal, absolute
