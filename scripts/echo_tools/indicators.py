"""Keep apps/backend/indicator_config.py in step with what is in the database.

This is the failure mode that produces no error message. INDICATOR_METADATA is a
hardcoded dict and main.py builds the API's indicator list straight from it, so
data loaded into results_data that has no entry here is simply invisible in the
dashboard — no warning, no empty state, nothing.

The database stores the *display name* in results_data.indicator_id, while the
config keys it by a short id. main.py bridges them with name_to_key_mapping.
That means the display name in the config must match the database string
exactly, so these commands offer it as a choice rather than asking anyone to
retype it.
"""
import importlib.util
import re
import shutil

from .config import INDICATOR_CONFIG, connection_url, describe_target, resolve_db_target
from .console import (ask, ask_yes_no, bad, choose, confirm, detail, die, ok,
                      say, step, warn)


def _load_config_module():
    """Import indicator_config.py from its path, fresh each time."""
    if not INDICATOR_CONFIG.exists():
        die("Missing {}".format(INDICATOR_CONFIG))
    spec = importlib.util.spec_from_file_location('_indicator_config', INDICATOR_CONFIG)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _database_indicators(target):
    """Return {display_name: sorted years} for everything in results_data."""
    try:
        from sqlalchemy import create_engine, text
    except ImportError:
        die("SQLAlchemy is not installed.",
            "cd packages/etl && pip install -r requirements.txt")

    engine = create_engine(connection_url(target))
    with engine.connect() as connection:
        rows = connection.execute(text("""
            SELECT indicator_id, array_agg(DISTINCT year ORDER BY year) AS years
            FROM results_data
            GROUP BY indicator_id
        """)).fetchall()
    return {row[0]: sorted(row[1]) for row in rows}


def _compare(config_metadata, db_indicators):
    """Work out the three ways config and data drift apart."""
    name_to_key = {meta['name']: key for key, meta in config_metadata.items()}

    missing_from_config = sorted(set(db_indicators) - set(name_to_key))
    missing_from_db = sorted(
        (key, meta['name']) for key, meta in config_metadata.items()
        if meta['name'] not in db_indicators)

    year_drift = []
    for name, db_years in db_indicators.items():
        key = name_to_key.get(name)
        if not key:
            continue
        declared = set(config_metadata[key].get('available_years', []))
        undeclared = sorted(set(db_years) - declared)
        if undeclared:
            year_drift.append((key, name, sorted(db_years), undeclared))

    return missing_from_config, missing_from_db, year_drift


def _report(target):
    module = _load_config_module()
    metadata = module.INDICATOR_METADATA

    step("Comparing database against indicator_config.py")
    detail(describe_target(target))

    db_indicators = _database_indicators(target)
    detail("{} indicators in the database, {} in the config".format(
        len(db_indicators), len(metadata)))

    missing_from_config, missing_from_db, year_drift = _compare(metadata, db_indicators)

    if missing_from_config:
        say()
        bad("{} indicator(s) in the database but NOT in indicator_config.py".format(
            len(missing_from_config)))
        detail("These are invisible in the dashboard. This is the silent failure.")
        for name in missing_from_config:
            say('    "{}"  years {}'.format(name, db_indicators[name]))

    if year_drift:
        say()
        bad("{} indicator(s) have data for years not listed in available_years".format(
            len(year_drift)))
        detail("The data is loaded but those years cannot be selected in the UI.")
        for key, name, _all_years, undeclared in year_drift:
            say("    {}: missing {}".format(key, undeclared))

    if missing_from_db:
        say()
        warn("{} indicator(s) in indicator_config.py with no data".format(len(missing_from_db)))
        detail("These appear in the UI but return nothing.")
        for key, name in missing_from_db:
            say('    {}  ("{}")'.format(key, name))

    say()
    if not (missing_from_config or year_drift or missing_from_db):
        ok("Config and database agree.")
    return metadata, db_indicators, missing_from_config, missing_from_db, year_drift


def check_indicators():
    """Read-only diff of the database against the config."""
    target = resolve_db_target()
    _, _, missing_from_config, _, year_drift = _report(target)

    if missing_from_config or year_drift:
        detail("Fix these with: python scripts/echo.py sync-indicators")
        return 1
    return 0


# --- editing indicator_config.py -------------------------------------------
#
# The dict is uniformly formatted, so the file is edited as text rather than
# rewritten from a parsed representation — that keeps comments, grouping and
# formatting exactly as they are. Every write is verified by re-importing.

def _matching_brace(text, open_index):
    """Index of the '}' matching the '{' at open_index."""
    depth = 0
    for i in range(open_index, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return i
    die("Could not parse indicator_config.py — unbalanced braces.")


def _entry_span(text, key):
    """(start, end) of the dict literal belonging to `key`."""
    match = re.search(r'^\s*["\']{}["\']\s*:\s*\{{'.format(re.escape(key)), text, re.MULTILINE)
    if not match:
        die("Could not find '{}' in indicator_config.py".format(key))
    open_index = text.index('{', match.start())
    return open_index, _matching_brace(text, open_index)


def _write_verified(new_text, expect_key):
    """Write the file, then prove it still imports and contains expect_key."""
    backup = INDICATOR_CONFIG.with_suffix('.py.bak')
    shutil.copy2(str(INDICATOR_CONFIG), str(backup))

    try:
        INDICATOR_CONFIG.write_text(new_text, encoding='utf-8')
        module = _load_config_module()
        if expect_key not in module.INDICATOR_METADATA:
            raise KeyError(expect_key)
    except Exception as exc:
        shutil.copy2(str(backup), str(INDICATOR_CONFIG))
        die("The edit produced a broken file, so it was rolled back ({}).".format(exc),
            "indicator_config.py is unchanged. Please report this.")
    finally:
        # Never leave a stray .bak in apps/backend/ — the Dockerfile does
        # `COPY . .`, so it would end up inside the deployed image.
        backup.unlink(missing_ok=True)

    ok("Updated {}".format(INDICATOR_CONFIG.name))


def _add_indicator(display_name, years, existing_themes):
    """Prompt for the parts that cannot be derived, then insert the entry."""
    say()
    step('Adding "{}"'.format(display_name))
    detail("Years found in the data: {}".format(years))

    suggested = re.sub(r'[^a-z0-9]+', '_', display_name.lower()).strip('_')[:40]
    key = ask("Short id used by the API (letters, numbers, underscores)", default=suggested)
    if not re.match(r'^[a-z][a-z0-9_]*$', key):
        die("'{}' is not a usable id.".format(key),
            "Use lowercase letters, numbers and underscores, starting with a letter.")

    theme = choose("Which theme does it belong to?", existing_themes, allow_new=True)
    description = ask("One-sentence description (shown in the dashboard)")

    entry = (
        '    "{key}": {{\n'
        '        "name": "{name}",\n'
        '        "theme": "{theme}",\n'
        '        "description": "{description}",\n'
        '        "available_years": {years}\n'
        '    }},\n'
    ).format(key=key, name=display_name, theme=theme,
             description=description.replace('"', "'"), years=years)

    say()
    say("This will be added to indicator_config.py:")
    say()
    say(entry.rstrip())
    confirm("Add this indicator?")

    text = INDICATOR_CONFIG.read_text(encoding='utf-8')
    open_index = text.index('{', text.index('INDICATOR_METADATA'))
    close_index = _matching_brace(text, open_index)
    new_text = text[:close_index] + entry + text[close_index:]
    _write_verified(new_text, key)
    return key


def _update_years(key, years):
    """Replace one entry's available_years with what the data actually contains."""
    text = INDICATOR_CONFIG.read_text(encoding='utf-8')
    start, end = _entry_span(text, key)
    block = text[start:end]

    if not re.search(r'"available_years"\s*:\s*\[[^\]]*\]', block):
        die("'{}' has no available_years to update.".format(key))

    new_block = re.sub(r'("available_years"\s*:\s*)\[[^\]]*\]',
                       lambda m: m.group(1) + str(years), block)
    _write_verified(text[:start] + new_block + text[end:], key)


def sync_indicators():
    """Interactively bring indicator_config.py in line with the database."""
    target = resolve_db_target()
    metadata, db_indicators, missing_from_config, _, year_drift = _report(target)

    if not (missing_from_config or year_drift):
        return 0

    # Years first: nothing needs typing, so the common case finishes fastest.
    for key, name, all_years, undeclared in year_drift:
        say()
        step("{} has data for {} which is not selectable".format(key, undeclared))
        detail('display name: "{}"'.format(name))
        detail("available_years would become {}".format(all_years))
        confirm("Update available_years for {}?".format(key))
        _update_years(key, all_years)

    if missing_from_config:
        themes = sorted({meta['theme'] for meta in metadata.values()})
        remaining = list(missing_from_config)
        while remaining:
            say()
            display_name = choose(
                "Which indicator should be added to the config?", remaining)
            _add_indicator(display_name, db_indicators[display_name], themes)
            remaining.remove(display_name)
            if remaining:
                say()
                say("{} indicator(s) still missing from the config.".format(len(remaining)))
                if not ask_yes_no("Add another?", default=True):
                    break

    say()
    step("Config updated. These changes are not live yet.")
    detail("The config is compiled into the running backend, so deploy it:")
    detail("  python scripts/echo.py deploy-backend")
    return 0
