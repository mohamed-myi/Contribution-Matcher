from __future__ import annotations

import core.api.github_api as github_api


class _MockResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_graphql_batch_fetch_uses_variables(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):  # noqa: ARG001
        captured["json"] = json
        return _MockResponse(
            200,
            {
                "data": {
                    "repo_0": {
                        "owner": {"login": "x"},
                        "name": "y",
                        "stargazerCount": 1,
                        "forkCount": 2,
                        "languages": {"edges": []},
                        "repositoryTopics": {"nodes": []},
                        "defaultBranchRef": None,
                    },
                    "repo_1": None,
                }
            },
        )

    # Force token presence so GraphQL path runs.
    monkeypatch.setattr(github_api, "_get_token", lambda: "token")
    monkeypatch.setattr(github_api.requests, "post", fake_post)

    repo_list = [
        ('o"wn', "na\nme"),
        ("owner2", "name2"),
    ]
    results = github_api._graphql_batch_fetch_repos(repo_list)

    # Basic result mapping still works.
    assert results[repo_list[0]] is not None
    assert results[repo_list[1]] is None

    body = captured["json"]
    assert isinstance(body, dict)
    assert "query" in body
    assert "variables" in body

    query = body["query"]
    variables = body["variables"]

    # Query should refer to variables, not contain raw values.
    assert "$owner0" in query
    assert "$name0" in query
    assert "$owner1" in query
    assert "$name1" in query
    assert 'o"wn' not in query
    assert "na\nme" not in query

    # Variables should carry original unescaped values.
    assert variables["owner0"] == 'o"wn'
    assert variables["name0"] == "na\nme"
    assert variables["owner1"] == "owner2"
    assert variables["name1"] == "name2"
