from hercules_cli.cooklabs_remote import (
    COOKLABS_HTTPS,
    canonical_github_remote,
    is_cooklabs_remote,
    preferred_remote_url,
)


def test_canonical_https_and_ssh():
    assert canonical_github_remote(
        "https://github.com/mintoriakamoto/Hercules.git"
    ) == "github.com/mintoriakamoto/hercules"
    assert canonical_github_remote(
        "git@github.com:mintoriakamoto/Hercules.git"
    ) == "github.com/mintoriakamoto/hercules"


def test_nous_is_not_cooklabs():
    assert not is_cooklabs_remote("https://github.com/NousResearch/hercules-agent.git")
    assert is_cooklabs_remote("https://github.com/mintoriakamoto/Hercules")


def test_prefer_ssh_when_origin_was_ssh():
    assert preferred_remote_url("git@github.com:NousResearch/hercules-agent.git").startswith("git@")
    assert preferred_remote_url("https://example/x") == COOKLABS_HTTPS
