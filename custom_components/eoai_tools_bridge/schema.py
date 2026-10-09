"""Make a metadata-only view without evaluating optional parameter defaults."""

from typing import Any

import probatio as vol

from .const import MAX_CATALOG_SCHEMA_DEPTH, MAX_CATALOG_SCHEMA_NODES


def parameters_without_defaults(parameters: Any) -> Any:
    """Keep native constraints; never compile, validate, or mutate a live schema.

    Only plain Optional defaults can be omitted without changing presence/group
    constraints. Required/group defaults and unknown marker subclasses fail
    closed. Schema/combinator views are uncompiled and used only by the codec.
    """
    remaining = MAX_CATALOG_SCHEMA_NODES
    marker_types = {
        vol.Marker,
        vol.Required,
        vol.Optional,
        vol.Exclusive,
        vol.Inclusive,
    }

    def copy_node(node: Any, depth: int) -> Any:
        nonlocal remaining
        remaining -= 1
        if remaining < 0 or depth > MAX_CATALOG_SCHEMA_DEPTH:
            raise ValueError("Oversized parameter definition")
        if isinstance(node, vol.Schema):
            if type(node) is not vol.Schema:
                raise ValueError("Unsupported Schema subclass")
            # Constructing Schema would compile validators, including arbitrary
            # __voluptuous_compile__ hooks. This view only carries codec fields.
            view = object.__new__(vol.Schema)
            view.schema = copy_node(node.schema, depth + 1)
            view.required = node.required
            view.extra = node.extra
            return view
        if isinstance(node, vol.Marker):
            if type(node) not in marker_types:
                raise ValueError("Unsupported parameter marker")
            default = getattr(node, "default", vol.UNDEFINED)
            if (
                not isinstance(default, vol.Undefined)
                and type(node) is not vol.Optional
            ):
                raise ValueError("Unsupported presence default")
            view = object.__new__(type(node))
            view.__dict__.update(node.__dict__)
            view.schema = copy_node(node.schema, depth + 1)
            if hasattr(node, "default"):
                view.default = vol.UNDEFINED
            return view
        if type(node) in {vol.All, vol.Any}:
            view = object.__new__(type(node))
            view.validators = [copy_node(child, depth + 1) for child in node.validators]
            view.required = node.required
            view.msg = node.msg
            return view
        if isinstance(node, dict):
            return {
                copy_node(key, depth + 1): copy_node(child, depth + 1)
                for key, child in node.items()
            }
        if isinstance(node, list | tuple):
            return type(node)(copy_node(child, depth + 1) for child in node)
        # Preserve selector/validator identity for HA's custom serializer. The
        # codec's strict mode rejects leaves it cannot represent faithfully.
        return node

    return copy_node(parameters, 0)
