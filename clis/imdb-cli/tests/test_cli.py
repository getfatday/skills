"""CLI smoke tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from click.testing import CliRunner
from gfd_imdb_cli.cli import cli

runner = CliRunner()


def test_version():
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


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


def _make_movie(movie_id: str = "0133093", **kwargs):
    """Create a mock Movie object."""
    m = MagicMock()
    m.movieID = movie_id
    defaults = {"title": "The Matrix", "year": 1999, "rating": 8.7}
    defaults.update(kwargs)
    m.get.side_effect = lambda k, default="": defaults.get(k, default)
    m.__getitem__ = lambda self, k: defaults[k]
    m.__contains__ = lambda self, k: k in defaults
    m.data = defaults
    return m


def _make_person(person_id: str = "0000206", **kwargs):
    """Create a mock Person object."""
    p = MagicMock()
    p.personID = person_id
    defaults = {"name": "Keanu Reeves", "birth date": "1964-09-02"}
    defaults.update(kwargs)
    p.get.side_effect = lambda k, default="": defaults.get(k, default)
    p.__getitem__ = lambda self, k: defaults[k]
    p.__contains__ = lambda self, k: k in defaults
    p.data = defaults
    return p


@patch("gfd_imdb_cli.search.get_client")
def test_search_movies(mock_get_client):
    ia = MagicMock()
    mock_get_client.return_value = ia
    ia.search_movie.return_value = [_make_movie()]
    result = runner.invoke(cli, ["search", "movies", "matrix", "--format", "json"])
    assert result.exit_code == 0
    assert "Matrix" in result.output


@patch("gfd_imdb_cli.search.get_client")
def test_search_people(mock_get_client):
    ia = MagicMock()
    mock_get_client.return_value = ia
    person = _make_person()
    person.get.side_effect = lambda k, default="": {
        "name": "Keanu Reeves",
        "known for": [],
    }.get(k, default)
    ia.search_person.return_value = [person]
    result = runner.invoke(cli, ["search", "people", "keanu", "--format", "json"])
    assert result.exit_code == 0
    assert "Keanu" in result.output


@patch("gfd_imdb_cli.movie.get_client")
def test_movie_info(mock_get_client):
    ia = MagicMock()
    mock_get_client.return_value = ia
    m = _make_movie()
    m.get.side_effect = lambda k, default="": {
        "title": "The Matrix",
        "year": 1999,
        "rating": 8.7,
        "votes": 1900000,
        "runtimes": ["136"],
        "genres": ["Action", "Sci-Fi"],
        "directors": [],
        "director": [],
        "writers": [],
        "writer": [],
        "cast": [],
        "plot": ["A computer hacker learns about the true nature of reality."],
    }.get(k, default)
    ia.get_movie.return_value = m
    result = runner.invoke(cli, ["movie", "info", "tt0133093", "--format", "json"])
    assert result.exit_code == 0
    assert "Matrix" in result.output


@patch("gfd_imdb_cli.movie.get_client")
def test_movie_info_strips_tt_prefix(mock_get_client):
    ia = MagicMock()
    mock_get_client.return_value = ia
    m = _make_movie()
    m.get.side_effect = lambda k, default="": {
        "title": "The Matrix",
        "year": 1999,
        "rating": 8.7,
        "votes": 0,
        "runtimes": [],
        "genres": [],
        "directors": [],
        "director": [],
        "writers": [],
        "writer": [],
        "cast": [],
        "plot": [],
    }.get(k, default)
    ia.get_movie.return_value = m
    result = runner.invoke(cli, ["movie", "info", "tt0133093", "--format", "json"])
    assert result.exit_code == 0
    # Verify tt prefix was stripped when calling get_movie
    ia.get_movie.assert_called_once_with("0133093")


@patch("gfd_imdb_cli.top.get_client")
def test_top_movies(mock_get_client):
    ia = MagicMock()
    mock_get_client.return_value = ia
    ia.get_top250_movies.return_value = [_make_movie()]
    result = runner.invoke(cli, ["top", "movies", "--limit", "1", "--format", "json"])
    assert result.exit_code == 0
    assert "Matrix" in result.output


@patch("gfd_imdb_cli.person.get_client")
def test_person_info(mock_get_client):
    ia = MagicMock()
    mock_get_client.return_value = ia
    p = _make_person()
    p.get.side_effect = lambda k, default="": {
        "name": "Keanu Reeves",
        "birth date": "1964-09-02",
        "birth notes": "Beirut, Lebanon",
        "mini biography": ["Canadian actor."],
        "filmography": {},
    }.get(k, default)
    ia.get_person.return_value = p
    result = runner.invoke(cli, ["person", "info", "nm0000206", "--format", "json"])
    assert result.exit_code == 0
    assert "Keanu" in result.output
