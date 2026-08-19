import re

from django.conf import settings

import pytest
from elasticsearch import BadRequestError, Elasticsearch
from elasticsearch_dsl import Document, Text
from elasticsearch_dsl import Index as DslIndex

from froide.helper.search import (
    SearchQuerySetWrapper,
    get_index,
    get_search_analyzer,
    get_search_quote_analyzer,
    get_text_analyzer,
)
from froide.helper.search.filters import BaseSearchFilterSet

from fragdenstaat_at.theme.tests.testdata.search_docs import search_docs


class TestDocument(Document):
    content = Text(
        analyzer=get_text_analyzer(),
        search_analyzer=get_search_analyzer(),
        search_quote_analyzer=get_search_quote_analyzer(),
        index_options="offsets",
    )


def _es_url():
    """Resolve the configured host rather than assuming localhost.

    DE hardcodes localhost:9200; in AT's devcontainer Elasticsearch is a
    separate service, so the host comes from DJANGO_ELASTICSEARCH_HOSTS via
    settings.es_hosts().
    """
    hosts = settings.ELASTICSEARCH_DSL["default"]["hosts"]
    if isinstance(hosts, (list, tuple)):
        hosts = hosts[0]
    if isinstance(hosts, dict):
        return "{}://{}:{}".format(
            hosts.get("scheme", "http"), hosts["host"], hosts.get("port", 9200)
        )
    return hosts if "://" in str(hosts) else f"http://{hosts}"


@pytest.fixture(scope="session")
def elasticsearch_client():
    """Skip, rather than error, when Elasticsearch is not running.

    These tests carry @pytest.mark.elasticsearch, but the marker only supports
    deselecting them by hand. Without this the whole module errors out on a
    machine where the service happens to be down, which is a bad default for a
    suite people run constantly.
    """
    client = Elasticsearch(_es_url())
    try:
        if not client.ping():
            raise ConnectionError("ping failed")
    except Exception as exc:
        pytest.skip(f"Elasticsearch unreachable at {_es_url()}: {exc}")
    return client


@pytest.fixture(scope="session")
def test_index(elasticsearch_client):  # noqa: ARG001 -- ordering/skip dependency
    # Set up the test index.
    index = get_index("docs")
    # Deliberately NOT index.document(...): froide's get_index() returns a
    # django_elasticsearch_dsl Index whose document() also calls
    # registry.register_document(), which requires a `class Django: model = ...`
    # and then wires that model into the global document registry for the whole
    # session. DE can afford it because it hands over fds_blog's Article; AT has
    # no fds_blog, and registering some unrelated model would mean every later
    # test that saves it tries to index into an index this fixture deletes on
    # teardown. Attaching the mapping via the plain elasticsearch_dsl base class
    # gives the tests what they need with no global side effect.
    DslIndex.document(index, TestDocument)
    # Timeout has to be set here - is ignored when set in Elasticsearch().
    try:
        index.create(timeout="60s")
    except BadRequestError:
        index.delete()
        index.create(timeout="60s")

    # Create test documents.
    for doc in search_docs:
        doc_id = doc.get("id")
        TestDocument(**doc).save(id=doc_id)

    TestDocument._index.refresh()

    yield index

    # Clean up after the test run.
    index.delete()


@pytest.fixture(scope="session")
def analyze(test_index):
    def _analyze(analyzer_name, text):
        result = test_index.analyze(
            body={"analyzer": analyzer_name, "text": text},
        )

        return [t["token"] for t in result["tokens"]]

    return _analyze


@pytest.fixture(scope="session")
def test_search_filterset():
    class TestSearchFilterSet(BaseSearchFilterSet):
        query_fields = ["content"]

    return TestSearchFilterSet


@pytest.fixture(scope="session")
def search(test_index, test_search_filterset):
    def _search(query):
        data = {}
        if query:
            data["q"] = query

        mock_model = type(
            "MockModel",
            (),
            {"_default_manager": type("Manager", (), {"all": lambda: None})},
        )

        search = test_index.search()
        search = search.highlight_options(encoder="html").highlight("content")

        sqs = SearchQuerySetWrapper(search, mock_model)
        filterset = test_search_filterset(data=data, queryset=sqs)

        results = list(filterset.qs)

        return transform_search_results(results)

    return _search


def transform_search_results(search_results):
    """
    Transform the raw Elasticsearch result into a more convenient format.

    Return a tuple of (`doc_ids`, `highlights`), where:
    - `doc_ids` is a list of document IDs that matched the query (in the order they were returned).
    - `highlights` is a list of lists, where each inner list contains the highlighted
      snippets for the corresponding document.
    """
    doc_ids = [hit.meta.id for hit in search_results]
    highlights = get_highlights(search_results)

    return doc_ids, highlights


def get_highlights(search_results):
    highlighted_texts = []
    for hit in search_results:
        if hasattr(hit.meta, "highlight") and hasattr(hit.meta.highlight, "content"):
            highlighted_texts.append(hit.meta.highlight.content)
        else:
            highlighted_texts.append([])

    highlights = [
        re.findall(r"<em>(.*?)</em>", " ".join(texts)) for texts in highlighted_texts
    ]

    return highlights


@pytest.fixture(scope="session")
def decompounder_ready(elasticsearch_client):
    """Skip when the running Elasticsearch ignores `no_sub_matches`.

    theme/search.py sets no_sub_matches=True on the hyphenation_decompounder to
    stop "formation"/"format"/"form" being pulled out of "Informationsfreiheit".
    Elasticsearch below 8.16 accepts the option and silently ignores it -- no
    error, just a noisier index -- so these tests would fail for an environment
    reason rather than a code one. deps/elasticsearch/Dockerfile pins 8.19.3;
    if this skips, the devcontainer needs rebuilding.
    """
    tokens = [
        t["token"]
        for t in elasticsearch_client.indices.analyze(
            body={
                "tokenizer": "standard",
                "filter": [
                    "lowercase",
                    {
                        "type": "hyphenation_decompounder",
                        "word_list_path": "analysis/dictionary-de.txt",
                        "hyphenation_patterns_path": "analysis/de_DR.xml",
                        "no_sub_matches": True,
                    },
                ],
                "text": "Informationsfreiheit",
            }
        )["tokens"]
    ]
    if "formation" in tokens:
        version = elasticsearch_client.info()["version"]["number"]
        pytest.skip(
            f"Elasticsearch {version} ignores hyphenation_decompounder's "
            "no_sub_matches (needs >= 8.16). Rebuild the devcontainer to pick up "
            "deps/elasticsearch/Dockerfile, which pins 8.19.3."
        )
