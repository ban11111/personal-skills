#!/usr/bin/env python3
"""Validate self-contained skills, catalog, metadata, links and common leaks."""
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit
import yaml

ROOT = Path(__file__).resolve().parents[1]
IGNORE = {'.git','.venv','__pycache__','out','artifacts'}
ID = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*')


def frontmatter(path):
    text = path.read_text()
    match = re.match(r'^---\n(.*?)\n---(?:\n|$)', text, re.S)
    if not match:
        raise ValueError(f'{path.name}: missing YAML frontmatter')
    value = yaml.safe_load(match.group(1))
    if not isinstance(value,dict):
        raise ValueError('frontmatter must be a mapping')
    return value, text[match.end():]


def validate(root=ROOT):
    root = root.resolve()
    errors = []
    catalog = json.loads((root/'catalog.json').read_text())
    if catalog['schemaVersion'] != 1:
        raise ValueError('unsupported catalog version')
    entries = catalog['skills']
    ids = [entry['id'] for entry in entries]
    if len(set(ids)) != len(ids):
        errors.append('duplicate catalog skill ids')
    actual = {path.parent.name for path in (root/'skills').glob('*/SKILL.md')}
    if actual != set(ids):
        errors.append('catalog and installed skill folders differ')
    for entry in entries:
        sid = entry['id']
        if not ID.fullmatch(sid) or len(sid)>64 or entry['path'] != f'skills/{sid}':
            errors.append(f'{sid}: invalid id or non-flat path')
            continue
        if not entry['category'] or not isinstance(entry['tags'],list):
            errors.append(f'{sid}: invalid category/tags')
        path = root/entry['path']
        if path.is_symlink():
            errors.append(f'{sid}: skill source cannot be a symlink')
            continue
        metadata, body = frontmatter(path/'SKILL.md')
        if metadata.get('name') != sid:
            errors.append(f'{sid}: frontmatter name mismatch')
        description = metadata.get('description')
        if not isinstance(description,str) or not description.strip() or len(description)>1024:
            errors.append(f'{sid}: invalid description')
        version = str(metadata.get('metadata',{}).get('version',''))
        if not re.fullmatch(r'\d+\.\d+\.\d+',version):
            errors.append(f'{sid}: metadata.version must be semantic version')
        if '[TODO:' in body or re.search(r'^#{1,6}.*TODO',body,re.M):
            errors.append(f'{sid}: unfinished scaffold')
        ui = yaml.safe_load((path/'agents/openai.yaml').read_text())['interface']
        if '$'+sid not in ui.get('default_prompt',''):
            errors.append(f'{sid}: prompt must mention skill')
        if not 25 <= len(ui.get('short_description','')) <= 64:
            errors.append(f'{sid}: short description must be 25–64 characters')
    manifest = json.loads((root/'.codex-plugin/plugin.json').read_text())
    if manifest.get('name') != root.name or manifest.get('skills') != './skills/':
        errors.append('plugin folder/name or skill root mismatch')
    interface = manifest.get('interface',{})
    for field in ('displayName','shortDescription','longDescription','developerName'):
        if not isinstance(interface.get(field),str) or not interface[field].strip():
            errors.append(f'plugin interface.{field} must be a nonempty string')
    for path in root.rglob('*'):
        relative = path.relative_to(root)
        if any(part in IGNORE for part in relative.parts) or not path.is_file():
            continue
        if path.is_symlink():
            errors.append(f'{relative}: symlink is not a portable repository artifact')
            continue
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        patterns = {
            'private key':r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
            'access token':r'\bgh[pousr]_[A-Za-z0-9]{30,}\b',
            'personal filesystem path':r'/(?:Users|home)/[A-Za-z0-9_.-]+/',
        }
        for label,pattern in patterns.items():
            if re.search(pattern,text):
                errors.append(f'{relative}: possible {label}')
        if path.suffix != '.md':
            continue
        for target in re.findall(r'\[[^\]\n]*\]\(([^)\n]+)\)',text):
            parsed = urlsplit(target.strip('<>'))
            if parsed.scheme or target.startswith('#'):
                continue
            resolved = (path.parent/unquote(parsed.path)).resolve()
            boundary = root
            if relative.parts[0] == 'skills' and len(relative.parts)>2:
                boundary = root/'skills'/relative.parts[1]
            if not resolved.is_relative_to(boundary) or not resolved.exists():
                errors.append(f'{relative}: broken or nonportable link {target}')
    return errors


def main():
    try:
        errors = validate()
    except (OSError,ValueError,KeyError,TypeError,yaml.YAMLError) as error:
        print(f'Invalid repository input: {error}', file=sys.stderr)
        return 2
    if errors:
        print('\n'.join(errors),file=sys.stderr)
        return 1
    print('Skill catalog, metadata, local links and common leak checks passed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
