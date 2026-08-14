"""Shared pytest fixtures and configuration.

All tests run against the real PostgreSQL instance defined by DATABASE_URL
(see .env / docker-compose). Integration tests are always included so the
ETL chain and repositories are covered by the same quality gate.
"""
