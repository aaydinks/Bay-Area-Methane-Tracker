"""Publish one run to the website's database (ADR 0009).

``build`` assembles a snapshot from ``data/interim``, ``data/processed``, the registry and
``reports/validation``, labels every check result, checks the wording of every text field and
writes the snapshot to ``data/processed/publications/<publish_id>/``. ``push`` loads it into the
database in one transaction with visibility ``draft``; ``set_visibility`` promotes it to
``review`` or ``public``. A simulated run can never be made public.
"""
