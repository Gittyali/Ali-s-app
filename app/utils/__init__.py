"""Utility layer: logging, filesystem paths, image helpers and threading.

Every other module builds on these primitives; nothing in here imports from
the rest of the application, which keeps the dependency graph acyclic.
"""
