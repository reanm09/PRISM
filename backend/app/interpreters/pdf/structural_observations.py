from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject


MAX_PDF_OBJECTS = 1024
MAX_PDF_DEPTH = 16
MAX_PDF_CHILDREN = 256
INCOMPLETE_WARNING = "PDF_SECURITY_OBSERVATION_INCOMPLETE"


def inspect_pdf_structure(reader) -> tuple[tuple[int | None, int | None, int | None], list[str]]:
    counts = [0, 0, 0]
    incomplete = False
    seen_refs = set()
    seen_objects = set()
    stack = [(reader.trailer.get("/Root"), 0, False)]
    visited = 0

    while stack:
        obj, depth, annotation = stack.pop()
        if depth > MAX_PDF_DEPTH or visited >= MAX_PDF_OBJECTS:
            incomplete = True
            break
        if isinstance(obj, IndirectObject):
            key = (obj.idnum, obj.generation)
            if key in seen_refs:
                continue
            seen_refs.add(key)
            try:
                obj = obj.get_object()
            except Exception:
                incomplete = True
                continue
        if obj is None or not isinstance(obj, (DictionaryObject, ArrayObject)):
            continue
        identity = id(obj)
        if identity in seen_objects:
            continue
        seen_objects.add(identity)
        visited += 1

        if isinstance(obj, DictionaryObject):
            action = obj.get("/S")
            if action == "/JavaScript":
                counts[0] += 1
            elif action == "/Launch":
                counts[1] += 1
            if obj.get("/Subtype") == "/RichMedia" and (annotation or obj.get("/Type") == "/Annot"):
                counts[2] += 1
            if len(obj) > MAX_PDF_CHILDREN:
                incomplete = True
                break
            for key, value in obj.items():
                stack.append((value, depth + 1, key == "/Annots"))
        else:
            if len(obj) > MAX_PDF_CHILDREN:
                incomplete = True
                break
            for value in obj:
                stack.append((value, depth + 1, annotation))

    if incomplete:
        return (None, None, None), [INCOMPLETE_WARNING]
    return (counts[0], counts[1], counts[2]), []
