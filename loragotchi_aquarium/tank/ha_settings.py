"""Translate Supervisor options into a complete, authoritative render profile.

No saved desktop settings/layout are merged into this profile. Optional graphics
overrides inherit from the selected preset when omitted (or cleared in HA).
"""
import json
import math
from pathlib import Path
from .settings import Settings, PRESETS


def boolean(value, name):
    if not isinstance(value, bool):
        raise ValueError(f'{name} must be true or false')
    return value


def render_settings(options):
    settings = Settings()
    preset = options.get('graphics_preset', 'balanced')
    if preset not in PRESETS:
        raise ValueError('Unknown graphics_preset')
    settings.apply(preset)
    for option, field, low, high, integer in (
        ('render_scale', 'scale', .25, 2., False),
        ('detail', 'detail', 8, 48, True),
        ('plants', 'plants', 0, 100, True),
        ('bubbles', 'bubbles', 0, 100, True),
        ('fps', 'fps', 10, 60, True),
    ):
        value = options.get(option, 20 if option == 'fps' else None)
        if value is None:
            continue
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or not low <= value <= high
                or (integer and not isinstance(value, int))):
            raise ValueError(f'{option} must be {low}..{high}' + (' (integer)' if integer else ''))
        setattr(settings, field, value)
    for name in ('lighting', 'caustics'):
        if options.get(name) is not None:
            setattr(settings, name, boolean(options[name], name))
    for name, default in (('vsync', False), ('chat_bubbles', True),
                          ('show_names', False), ('fish_animations', True)):
        setattr(settings, name, boolean(options.get(name, default), name))
    # Read library defaults without importing Panda3D into the supervisor.
    defaults = {}
    for path in sorted((Path(__file__).parent/'assets'/'decorations').glob('*/decoration.json')):
        defaults[path.parent.name] = json.loads(path.read_text())['enabled']
    for name, values in (('decorations', defaults),
                         ('exit_styles', dict.fromkeys(('shark', 'net', 'bag', 'bowl', 'cage'), True))):
        supplied = options.get(name, {})
        if not isinstance(supplied, dict) or supplied.keys() - values.keys():
            raise ValueError(f'Unknown {name} selection')
        values.update({key: boolean(value, f'{name}.{key}') for key, value in supplied.items()})
        setattr(settings, name, values)
    return settings
