"""Provider selection: real external clients when keys exist, mocks otherwise.

This is the seam that lets the whole journey run locally today and switch to
real OpenAI/Apify/Places by just setting a key (Bloco 5).
"""
from dataclasses import dataclass

from app.config import settings
from app.providers import mock
from app.providers.base import Cleaner, Discovery, Enrichment, ReportParser
from app.providers.report_parser import HeuristicReportParser


@dataclass
class Providers:
    discovery: Discovery
    enrichment: Enrichment
    cleaner: Cleaner


def get_providers() -> Providers:
    if settings.openai_api_key and settings.apify_token:
        # Real clients land here in Bloco 5; until then, mocks.
        return Providers(mock.MockDiscovery(), mock.MockEnrichment(), mock.MockCleaner())
    return Providers(mock.MockDiscovery(), mock.MockEnrichment(), mock.MockCleaner())


def get_report_parser() -> ReportParser:
    # Heuristic parser needs no key; an LLM parser upgrades it in Bloco 5.
    return HeuristicReportParser()
