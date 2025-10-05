import pytest
from teamskills.backend.github_scraper import summarize_user

# Simple smoke test: ensure summarize_user returns expected keys for a public user
@pytest.mark.parametrize("username", ["yc73080"])
def test_summarize_user_basic(username):
    res = summarize_user(username)
    assert isinstance(res, dict)
    assert res.get("username") == username
    assert "overall_language_percentages" in res
    assert isinstance(res.get("repos", []), list)
