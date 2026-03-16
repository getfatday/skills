"""CLI smoke tests."""

from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner
from gfd_imdb_cli.cli import cli

runner = CliRunner()


def test_version():
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.2.0" in result.output


def test_help():
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "IMDB data CLI" in result.output


def test_command_groups_registered():
    result = runner.invoke(cli, ["--help"])
    for group in ["search", "movie", "person", "top", "upcoming"]:
        assert group in result.output, f"Missing command group: {group}"


def test_search_movies_help():
    result = runner.invoke(cli, ["search", "movies", "--help"])
    assert result.exit_code == 0
    assert "Search movies by title" in result.output


def test_search_people_help():
    result = runner.invoke(cli, ["search", "people", "--help"])
    assert result.exit_code == 0
    assert "Search people by name" in result.output


def test_movie_info_help():
    result = runner.invoke(cli, ["movie", "info", "--help"])
    assert result.exit_code == 0


def test_movie_cast_help():
    result = runner.invoke(cli, ["movie", "cast", "--help"])
    assert result.exit_code == 0


def test_movie_box_office_help():
    result = runner.invoke(cli, ["movie", "box-office", "--help"])
    assert result.exit_code == 0


def test_person_info_help():
    result = runner.invoke(cli, ["person", "info", "--help"])
    assert result.exit_code == 0


def test_person_filmography_help():
    result = runner.invoke(cli, ["person", "filmography", "--help"])
    assert result.exit_code == 0


def test_top_movies_help():
    result = runner.invoke(cli, ["top", "movies", "--help"])
    assert result.exit_code == 0


def test_top_shows_help():
    result = runner.invoke(cli, ["top", "shows", "--help"])
    assert result.exit_code == 0


def test_top_box_office_help():
    result = runner.invoke(cli, ["top", "box-office", "--help"])
    assert result.exit_code == 0


def test_upcoming_help():
    result = runner.invoke(cli, ["upcoming", "--help"])
    assert result.exit_code == 0


# --- Functional tests with mocked HTTP ---


@patch("gfd_imdb_cli.client.search_suggestions")
def test_search_movies(mock_search):
    mock_search.return_value = [
        {
            "id": "tt0133093", "l": "The Matrix", "y": 1999,
            "q": "feature", "qid": "movie", "s": "Keanu Reeves",
        },
    ]
    result = runner.invoke(cli, ["search", "movies", "matrix", "--format", "json"])
    assert result.exit_code == 0
    assert "Matrix" in result.output


@patch("gfd_imdb_cli.client.search_suggestions")
def test_search_people(mock_search):
    mock_search.return_value = [
        {"id": "nm0000206", "l": "Keanu Reeves", "s": "Actor, The Matrix (1999)"},
    ]
    result = runner.invoke(cli, ["search", "people", "keanu", "--format", "json"])
    assert result.exit_code == 0
    assert "Keanu" in result.output


@patch("gfd_imdb_cli.client.get_title")
def test_movie_info(mock_get_title):
    mock_get_title.return_value = {
        "id": "tt0133093",
        "titleText": {"text": "The Matrix"},
        "releaseYear": {"year": 1999},
        "ratingsSummary": {"aggregateRating": 8.7, "voteCount": 1900000},
        "runtime": {"seconds": 8160},
        "genres": {"genres": [{"text": "Action"}, {"text": "Sci-Fi"}]},
        "directors": {"edges": []},
        "writers": {"edges": []},
        "cast": {"edges": []},
        "plot": {
            "plotText": {
                "plainText": "A hacker learns about reality.",
            },
        },
    }
    result = runner.invoke(cli, ["movie", "info", "tt0133093", "--format", "json"])
    assert result.exit_code == 0
    assert "Matrix" in result.output


@patch("gfd_imdb_cli.movie.get_title")
def test_movie_info_strips_tt_prefix(mock_get_title):
    mock_get_title.return_value = {
        "id": "tt0133093",
        "titleText": {"text": "The Matrix"},
        "releaseYear": {"year": 1999},
        "ratingsSummary": {"aggregateRating": 8.7, "voteCount": 0},
        "runtime": None,
        "genres": {"genres": []},
        "directors": {"edges": []},
        "writers": {"edges": []},
        "cast": {"edges": []},
        "plot": None,
    }
    result = runner.invoke(cli, ["movie", "info", "tt0133093", "--format", "json"])
    assert result.exit_code == 0
    # Verify tt prefix was kept for GraphQL
    mock_get_title.assert_called_once_with("tt0133093")


@patch("gfd_imdb_cli.top.get_top_movies")
def test_top_movies(mock_get_top):
    mock_get_top.return_value = [
        {
            "currentRank": 1,
            "node": {
                "id": "tt0133093",
                "titleText": {"text": "The Matrix"},
                "releaseYear": {"year": 1999},
                "ratingsSummary": {"aggregateRating": 8.7},
            },
        },
    ]
    result = runner.invoke(cli, ["top", "movies", "--limit", "1", "--format", "json"])
    assert result.exit_code == 0
    assert "Matrix" in result.output


@patch("gfd_imdb_cli.client.get_person")
def test_person_info(mock_get_person):
    mock_get_person.return_value = {
        "id": "nm0000206",
        "nameText": {"text": "Keanu Reeves"},
        "birthDate": {"dateComponents": {"year": 1964, "month": 9, "day": 2}},
        "birthLocation": {"text": "Beirut, Lebanon"},
        "bio": {"text": {"plainText": "Canadian actor."}},
        "knownFor": {"edges": []},
    }
    result = runner.invoke(cli, ["person", "info", "nm0000206", "--format", "json"])
    assert result.exit_code == 0
    assert "Keanu" in result.output
