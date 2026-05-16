"""Basic import tests for Strata.

Validates that core modules can be imported without errors.
"""

def test_import_package():
    """Test that the strata package imports with version."""
    from strata import __version__
    assert __version__ == "0.7.0"


def test_import_config():
    """Test that the config module imports."""
    from strata.config import Settings, get_settings
    assert Settings is not None
    assert callable(get_settings)


def test_import_schema():
    """Test that the schema module imports with rubric classes."""
    from strata.schema import (
        Attribute,
        Characteristic,
        Group,
        Rubric,
        RubricScoreReport,
        CharacteristicScore,
    )
    assert Attribute is not None
    assert Characteristic is not None
    assert Group is not None
    assert Rubric is not None
    assert RubricScoreReport is not None
    assert CharacteristicScore is not None


def test_attribute_creation():
    """Test Attribute model creation."""
    from strata.schema import Attribute
    attr = Attribute(level="Mature", score=4, anchor="Fully implemented with documentation")
    assert attr.score == 4


def test_settings_dataclass():
    """Test Settings dataclass has expected properties."""
    from strata.config import Settings
    # Settings requires database_url, so check the class exists
    import dataclasses
    fields = {f.name for f in dataclasses.fields(Settings)}
    assert "database_url" in fields
    assert "llm_backend" in fields
    assert "grader_model" in fields
