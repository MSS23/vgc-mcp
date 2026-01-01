# tests/ - Test Suite

Pytest test suite with 289 tests covering all calculations and tools.

## Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_damage.py -v

# Run specific test
python -m pytest tests/test_matchup.py::TestSingleMatchup::test_type_advantage -v

# Run with coverage
python -m pytest tests/ --cov=vgc_mcp

# Run tests matching pattern
python -m pytest tests/ -k "speed" -v
```

## Test Files

| File | Tests | Description |
|------|-------|-------------|
| `test_damage.py` | Damage formula, modifiers, KO calcs |
| `test_stats.py` | Stat calculations, nature modifiers |
| `test_team.py` | Team manager, species clause |
| `test_matchup.py` | Matchup scoring |
| `test_coverage.py` | Type coverage analysis |
| `test_speed_control.py` | Trick Room, Tailwind |
| `test_speed_probability.py` | Outspeed calculations |
| `test_bulk_optimization.py` | EV optimization |
| `test_abilities.py` | Ability synergy |
| `test_priority.py` | Priority move ordering |
| `test_legality.py` | VGC rules validation |
| `test_learnset.py` | Move learnset validation |
| `test_core_builder.py` | Core synergy |
| `test_showdown_parser.py` | Paste parsing |

## Configuration

### conftest.py

Shared fixtures for all tests:

```python
# Common fixtures
@pytest.fixture
def team_manager():
    return TeamManager()

@pytest.fixture
def flutter_mane_stats():
    return BaseStats(hp=55, attack=55, defense=55,
                     special_attack=135, special_defense=135, speed=135)
```

### pyproject.toml

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

## Test Patterns

### Creating Test Pokemon

```python
def make_pokemon(name, types, base_hp=80, base_atk=100, ...):
    return PokemonBuild(
        name=name,
        base_stats=BaseStats(hp=base_hp, attack=base_atk, ...),
        nature=Nature.SERIOUS,
        evs=EVSpread(),
        types=types
    )

# Usage
attacker = make_pokemon("Test", ["Fire"], base_spa=130)
```

### Testing Damage Calculations

```python
def test_stab_bonus():
    """Fire move from Fire type gets STAB."""
    attacker = make_pokemon("Charizard", ["Fire", "Flying"])
    defender = make_pokemon("Target", ["Normal"])
    move = Move(name="flamethrower", type="Fire", ...)

    result = calculate_damage(attacker, defender, move, DamageModifiers())

    # STAB should be applied
    assert "STAB" in result.details.get("modifiers_applied", [])
```

### Testing with Fixtures

```python
def test_species_clause(team_manager):
    """Can't add duplicate species."""
    pokemon1 = make_pokemon("Pikachu", ["Electric"])
    pokemon2 = make_pokemon("Pikachu", ["Electric"])

    team_manager.add_pokemon(pokemon1)

    with pytest.raises(TeamValidationError):
        team_manager.add_pokemon(pokemon2)
```

## Coverage Goals

- Damage formula: 100% coverage of modifiers
- Type chart: All 324 type combinations
- Stats: All nature modifiers
- Team: Species clause edge cases
- Legality: All restricted Pokemon
