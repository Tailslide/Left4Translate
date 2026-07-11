"""Unit tests for TranslationService (single-call detection, rate limiting,
slang post-pass, caching). All HTTP is mocked."""

from __future__ import annotations

import importlib
import sys
from unittest import mock

import pytest


@pytest.fixture
def svc_module():
    sys.modules.pop("translator.translation_service", None)
    sys.modules.pop("translator", None)
    return importlib.import_module("translator.translation_service")


@pytest.fixture
def service(svc_module):
    return svc_module.TranslationService(api_key="test-key", target_language="en")


def _response(translated: str, detected: str | None = None, status: int = 200):
    resp = mock.Mock()
    resp.status_code = status
    body = {"translatedText": translated}
    if detected is not None:
        body["detectedSourceLanguage"] = detected
    resp.json.return_value = {"data": {"translations": [body]}}
    return resp


def test_single_api_call_with_server_side_detection(svc_module, service):
    with mock.patch.object(svc_module.requests, "post") as post:
        post.return_value = _response("hello world", detected="fr")
        translated, source = service.translate_with_detection("bonjour le monde")

    assert translated == "hello world"
    assert source == "fr"
    assert post.call_count == 1, "translation must be a single API round-trip"
    # No 'source' param: server-side auto-detection was used.
    assert "source" not in post.call_args.kwargs["json"]


def test_already_target_language_returns_original(svc_module, service):
    with mock.patch.object(svc_module.requests, "post") as post:
        post.return_value = _response("greetings friend", detected="en")
        translated, source = service.translate_with_detection("greetings friend")

    assert translated == "greetings friend"
    assert source == "en"


def test_spanish_hint_passed_as_source(svc_module, service):
    # "hola" is a local Spanish indicator: the request should pin source=es
    # rather than paying for server-side detection ambiguity.
    with mock.patch.object(svc_module.requests, "post") as post:
        post.return_value = _response("hello friend how are you")
        translated, source = service.translate_with_detection("hola amigo como estas")

    assert translated == "hello friend how are you"
    assert source == "es"
    assert post.call_args.kwargs["json"]["source"] == "es"


def test_slang_postpass_position_independent(svc_module, service):
    # Google dropped a word (word counts differ) but left "manco" unchanged;
    # the old zip()-based pass would have compared wrong indices.
    with mock.patch.object(svc_module.requests, "post") as post:
        post.return_value = _response("the manco is here", detected="es")
        translated, _ = service.translate_with_detection("el manco esta aqui ya")

    assert translated == "the noob is here"


def test_slang_postpass_leaves_translated_words_alone(service):
    # "rico" translated to "rich" → must NOT be slang-substituted.
    out = service._apply_slang_postpass("que rico dia", "what a rich day")
    assert out == "what a rich day"


def test_rate_limit_exhaustion_returns_original(svc_module, service):
    service.rate_limit_wait_seconds = 0.2
    service.rate_limiter.rate_limit = 0
    service.rate_limiter.tokens = 0
    with mock.patch.object(svc_module.requests, "post") as post:
        translated, source = service.translate_with_detection("bonjour tout le monde")

    assert translated == "bonjour tout le monde"
    assert source is None
    post.assert_not_called()


def test_result_is_cached(svc_module, service):
    with mock.patch.object(svc_module.requests, "post") as post:
        post.return_value = _response("hello world", detected="fr")
        first = service.translate_with_detection("bonjour le monde")
        second = service.translate_with_detection("bonjour le monde")

    assert first == second == ("hello world", "fr")
    assert post.call_count == 1, "second lookup must come from the cache"


def test_translate_wrapper_returns_text_only(svc_module, service):
    with mock.patch.object(svc_module.requests, "post") as post:
        post.return_value = _response("hello", detected="fr")
        assert service.translate("bonjour le monde") == "hello"


def test_requests_carry_a_timeout(svc_module, service):
    with mock.patch.object(svc_module.requests, "post") as post:
        post.return_value = _response("hi", detected="fr")
        service.translate_with_detection("bonjour le monde")
    assert post.call_args.kwargs["timeout"] == svc_module.REQUEST_TIMEOUT_SECONDS
