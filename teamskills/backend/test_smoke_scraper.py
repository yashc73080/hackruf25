import os
import pytest
from github_scraper import summarize_user

# Lightweight smoke test. Uses public data and does not require secrets.
@pytest.mark.parametrize("username", ["yc73080", "ayushmish605"])
def test_summarize_user_basic(username):
    res = summarize_user(username)
    assert isinstance(res, dict)
    assert res.get("username") == username
    assert "overall_language_percentages" in res
    assert isinstance(res["overall_language_percentages"], list)
    assert "repos" in res
    assert isinstance(res["repos"], list)
