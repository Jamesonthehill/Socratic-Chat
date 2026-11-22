"""Source binding for optional instructor-reviewed SDL additions."""
import hashlib
import json


def expansion_source_hash(material, config):
    scope = {key: config.get(key, '') for key in ('starting_point', 'ending_point', 'prompt')}
    return hashlib.sha256(json.dumps({'material': material, 'scope': scope}, sort_keys=True).encode()).hexdigest()


def checked_expansion(material, config, plan=None):
    additions = config.get('material_expansion', '').strip()
    if additions:
        if not config.get('expansion_approved'):
            raise ValueError('Review and approve the additional material before preparing the lesson.')
        if config.get('expansion_source_hash') != expansion_source_hash(material, config):
            raise ValueError('The materials or learning scope changed. Generate a new expansion or remove the previous additions.')
    if plan is not None and plan.get('supplemental_material', '') != additions:
        raise ValueError('The additions changed. Review the activity again before publishing.')
    return additions
