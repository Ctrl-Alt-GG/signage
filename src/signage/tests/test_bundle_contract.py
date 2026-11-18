"""Every bundle the API answers with matches the schema the display's types are generated
from: each pass has the layout and the live data of its source."""

import httpx
import pytest
import respx
from django.core.cache import cache
from drf_spectacular.generators import SchemaGenerator
from jsonschema import Draft202012Validator

from signage.api.serializers import PASS_SERIALIZERS
from signage.content import lint
from signage.content.lint import LAYOUT_SOURCES
from signage.models import Event, Phase, Slide
from signage.tests.helpers import BRACKET, configure


@pytest.fixture(scope="module")
def bundle_schema():
    document = SchemaGenerator().get_schema(request=None, public=True)
    # The schema's own references point into its components.
    schema = {"$ref": "#/components/schemas/Bundle", "components": document["components"]}
    return Draft202012Validator(schema)


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


def in_phase(key: str) -> None:
    event = Event.get_solo()
    event.phase_mode = Event.PhaseMode.MANUAL
    event.current_phase = Phase.objects.get(key=key)
    event.save()


def assert_valid(validator, bundle) -> None:
    problems = [f"{list(error.path)}: {error.message}" for error in validator.iter_errors(bundle)]
    assert not problems, problems


@respx.mock
def test_every_live_source_answers_as_the_schema_says(client, content, fixture_json, bundle_schema):
    configure("projectile", "https://servers.example/api")
    configure("bracket", BRACKET, tournament_id=1)
    configure("streams", "https://streams.example/api/v1")
    respx.get("https://servers.example/api/bundle").respond(
        json=fixture_json("projectile_bundle.json")
    )
    respx.get(f"{BRACKET}/tournaments/1/details").respond(json=fixture_json("bracket_details.json"))
    respx.get("https://streams.example/api/v1/streams/").respond(
        json=fixture_json("streams_list.json")
    )
    in_phase("tournament")
    bundle = client.get("/api/v1/screens/main/bundle/").json()
    assert_valid(bundle_schema, bundle)
    sources = {pass_["source"] for pass_ in bundle["passes"]}
    assert {"static", "live:schedule", "live:projectile", "live:bracket", "live:streams"} <= sources
    for pass_ in bundle["passes"]:
        assert LAYOUT_SOURCES[pass_["layout"]] == pass_["source"]


@respx.mock
def test_upstream_systems_with_nothing_to_show_answer_as_the_schema_says(
    client, content, bundle_schema
):
    for kind, url in (
        ("projectile", "https://servers.example/api"),
        ("streams", "https://streams.example/api/v1"),
    ):
        configure(kind, url)
    respx.get("https://servers.example/api/bundle").respond(503)
    respx.get("https://streams.example/api/v1/streams/").mock(
        return_value=httpx.Response(
            200, json={"source": {"status": "unavailable", "observed_at": None}, "results": []}
        )
    )
    in_phase("play")
    assert_valid(bundle_schema, client.get("/api/v1/screens/main/bundle/").json())


def test_the_countdown_answers_as_the_schema_says(client, content, bundle_schema):
    in_phase("setup")
    event = Event.get_solo()
    event.starts_at = event.starts_at.replace(year=event.starts_at.year + 1)
    event.ends_at = event.ends_at.replace(year=event.ends_at.year + 1)
    event.save()
    bundle = client.get("/api/v1/screens/main/bundle/").json()
    assert "live:clock" in {pass_["source"] for pass_ in bundle["passes"]}
    assert_valid(bundle_schema, bundle)


def test_the_admin_the_import_and_the_schema_know_the_same_layouts_and_sources():
    # The admin offers the model's choices, the import checks against the matrix, and the
    # display draws what the schema describes: a name added to one of them only would be
    # accepted by one and refused, or drawn as something else, by another.
    assert set(Slide.Layout.values) == lint.LAYOUTS
    assert set(Slide.Source.values) == lint.SOURCES == set(PASS_SERIALIZERS)
