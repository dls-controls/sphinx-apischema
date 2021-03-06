import dataclasses
import inspect
from typing import Any, Dict, Iterator, Tuple

from apischema.json_schema.schema import Schema
from apischema.metadata.keys import SCHEMA_METADATA
from typing_extensions import Annotated, get_args, get_origin, get_type_hints

from ._version_git import __version__


def get_type_description(typ) -> Tuple[Any, str]:
    description = ""
    if get_origin(typ) == Annotated:
        typ, *args = get_args(typ)
        additional = []
        for arg in args:
            arg = arg.get(SCHEMA_METADATA, arg)
            if isinstance(arg, Schema):
                field_schema: Dict[str, Any] = {}
                arg.merge_into(field_schema)
                for key, value in field_schema.items():
                    if key == "description":
                        description = value
                    else:
                        additional.append(f"{str(key)}: {str(value)}")
        if additional:
            description = description + " - " + ", ".join(additional)
    return typ, description


@dataclasses.dataclass
class Param:
    name: str
    default: Any
    type: Any
    description: str


def get_params(what: str, obj) -> Iterator[Param]:
    if what == "class" and dataclasses.is_dataclass(obj):
        # If we are a dataclass, use this
        hints = get_type_hints(obj, include_extras=True)
        for field in dataclasses.fields(obj):
            yield Param(
                field.name, field.default, *get_type_description(hints.get(field.name))
            )
    elif what in ("method", "function"):
        hints = get_type_hints(obj, include_extras=True)
        parameters = list(inspect.signature(obj).parameters.values())
        if _is_bound.get(obj, False) and not inspect.ismethod(obj) and parameters:
            # Bound method which is not detected as such by inspect and has params,
            # remove the first arg (which is normally cls or self)
            parameters.pop(0)
        for param in parameters:
            default = param.default
            if default is inspect.Parameter.empty:
                default = dataclasses.MISSING
            yield Param(
                param.name, default, *get_type_description(hints.get(param.name))
            )


def process_docstring(app, what, name, obj, options, lines):
    params = list(get_params(what, obj))
    # If we added descriptions, then add param info
    if [p for p in params if p.description]:
        try:
            index = lines.index("") + 1
        except ValueError:
            lines.append("")
            index = len(lines)
        # Add types from each field
        for param in params:
            typ = getattr(param.type, "__name__", str(param.type)).replace(" ", "")
            lines.insert(index, f":param {typ} {param.name}: {param.description}")
            index += 1
        lines.insert(index, "")


_is_bound = {}


def before_process_signature(app, obj, bound_method):
    _is_bound[obj] = bound_method


def process_signature(app, what, name, obj, options, signature, return_annotation):
    params = list(get_params(what, obj))
    if [p for p in params if p.description]:
        # Recreate signature from the Param objects
        args = []
        for param in params:
            arg = param.name
            if param.default is not dataclasses.MISSING:
                arg += f"={param.default!r}"
            args.append(arg)
        signature = f'({", ".join(args)})'
    return signature, return_annotation


def setup(app):
    app.connect("autodoc-before-process-signature", before_process_signature)
    app.connect("autodoc-process-signature", process_signature)
    app.connect("autodoc-process-docstring", process_docstring)

    return {
        "version": __version__,
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
