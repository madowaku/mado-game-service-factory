"""Offline, opt-in audio import for Godot 4. Never writes to a project by default."""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import wave
import zipfile

MAX_ZIP = 100 * 1024 * 1024
MAX_ENTRY = 30 * 1024 * 1024
MAX_FILES = 200
DEST = Path('audio/mgsf_sound_identity')


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _name(raw: str) -> str:
    """Reject ZIP traversal, Windows drive/ADS, hidden and ambiguous components."""
    if not raw or '\x00' in raw or any(ord(c) < 32 for c in raw):
        raise ValueError('unsafe ZIP entry')
    raw = raw.replace('\\', '/')
    parts = PurePosixPath(raw).parts
    if raw.startswith('/') or not parts or any(x in ('', '.', '..') or x.startswith('.') or ':' in x for x in parts):
        raise ValueError('unsafe ZIP entry')
    if any(x.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *[f'COM{i}' for i in range(1, 10)], *[f'LPT{i}' for i in range(1, 10)]} for x in parts):
        raise ValueError('reserved ZIP entry')
    return '/'.join(parts)


def _wav(data: bytes) -> dict:
    with wave.open(io.BytesIO(data), 'rb') as f:
        channels, width, rate, frames = f.getnchannels(), f.getsampwidth(), f.getframerate(), f.getnframes()
        if f.getcomptype() != 'NONE' or channels not in (1, 2) or width not in (1, 2, 3, 4) or not 8000 <= rate <= 192000 or frames > 20_000_000:
            raise ValueError('unsupported PCM WAV')
        samples = f.readframes(frames)
    if len(samples) != channels * width * frames:
        raise ValueError('truncated PCM WAV')
    full = float(1 << (width * 8 - 1))
    total = 0.0
    peak = 0.0
    first = last = None
    count = 0
    for pos in range(0, len(samples), width * channels):
        values = []
        for ch in range(channels):
            b = samples[pos + ch * width: pos + (ch + 1) * width]
            value = (b[0] - 128) if width == 1 else int.from_bytes(b, 'little', signed=True)
            v = value / full
            values.append(v)
            peak = max(peak, abs(v))
            total += v * v
            count += 1
        mono = sum(values) / channels
        if first is None:
            first = mono
        last = mono
    rms = math.sqrt(total / count) if count else 0.0
    warnings = []
    if rms < 0.0001:
        warnings.append('silence_or_near_silence')
    if peak >= 0.999:
        warnings.append('possible_clipping')
    if first is not None and last is not None and abs(first - last) > 0.08:
        warnings.append('loop_boundary_discontinuity_heuristic')
    return {'channels': channels, 'sample_rate': rate, 'bit_depth': width * 8,
            'seconds': round(frames / rate, 3), 'rms': round(rms, 5),
            'peak': round(peak, 5), 'warnings': warnings}


def _read_zip(source: Path) -> tuple[str, list[dict], dict[str, bytes]]:
    if not source.is_file() or source.stat().st_size > MAX_ZIP or not zipfile.is_zipfile(source):
        raise ValueError('expected bounded ZIP archive')
    records, payloads, seen = [], {}, set()
    with zipfile.ZipFile(source) as z:
        files = [f for f in z.infolist() if not f.is_dir()]
        if len(files) > MAX_FILES or sum(f.file_size for f in files) > MAX_ZIP:
            raise ValueError('ZIP size/count limit exceeded')
        for item in files:
            name = _name(item.filename)
            if name.casefold() in seen or item.file_size > MAX_ENTRY:
                raise ValueError('duplicate ZIP entry or entry too large')
            seen.add(name.casefold())
            # Unix symlink: never follow or treat it as an ordinary file.
            if (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('ZIP symlink forbidden')
            suffix = PurePosixPath(name).suffix.lower()
            if suffix not in ('.wav', '.mid', '.midi', '.json'):
                continue
            data = z.read(item)
            rec = {'source': name, 'kind': suffix[1:], 'bytes': len(data), 'sha256': _sha(data)}
            if suffix == '.wav':
                try:
                    rec['audio'] = _wav(data)
                    payloads[name] = data
                except (ValueError, wave.Error, EOFError, OSError):
                    rec['error'] = 'invalid_or_unsupported_wav'
            records.append(rec)
    return _sha(source.read_bytes()), records, payloads


def _scene_map(path: Path | None, available: set[str]) -> tuple[dict[str, str], set[str]]:
    if path is None:
        return {}, set()
    spec = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(spec, dict) or spec.get('schema') != 'mgsf.sound_identity.scene_map.v0.2':
        raise ValueError('invalid scene map schema')
    scenes, loops = spec.get('scenes', {}), spec.get('loops', [])
    if not isinstance(scenes, dict) or not isinstance(loops, list) or not all(isinstance(x, str) for x in loops):
        raise ValueError('invalid scene map fields')
    for scene, source in scenes.items():
        if not isinstance(scene, str) or not scene.startswith('res://') or not scene.endswith('.tscn') or '..' in PurePosixPath(scene[6:]).parts or not isinstance(source, str) or source not in available:
            raise ValueError('invalid scene or missing WAV in scene map')
    if any(x not in available for x in loops):
        raise ValueError('loop references missing WAV')
    return scenes, set(loops)


def _slug(text: str) -> str:
    return re.sub('[^a-z0-9]+', '_', text.lower()).strip('_')[:45] or 'track'


def _target_ok(project: Path, rel: Path) -> Path:
    """No existing symlink in target ancestry, no existing output file."""
    current = project
    if project.is_symlink():
        raise ValueError('symlinked project forbidden')
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError('symlink in project output path')
    if current.exists():
        raise ValueError(f'asset already exists: {rel}')
    return current


def analyze_package(source: str | Path, project: str | Path, scene_map: str | Path | None = None) -> tuple[dict, dict[str, bytes]]:
    source, project = Path(source), Path(project)
    if not project.is_dir() or not (project / 'project.godot').is_file():
        raise ValueError('expected Godot project containing project.godot')
    archive_sha, records, payloads = _read_zip(source)
    scenes, loops = _scene_map(Path(scene_map) if scene_map else None, set(payloads))
    flags = sorted({w for r in records for w in r.get('audio', {}).get('warnings', [])})
    if not payloads:
        flags.append('no_valid_wav')
    if any('error' in r for r in records):
        flags.append('invalid_wav_present')
    hold = any(x in flags for x in ('no_valid_wav', 'invalid_wav_present', 'silence_or_near_silence'))
    status = 'HOLD' if hold else 'REVIEW' if flags else 'PASS'
    tracks = []
    for name, data in sorted(payloads.items()):
        name_hash = _sha(data)
        filename = f'{_slug(PurePosixPath(name).stem)}_{name_hash[:16]}.wav'
        tracks.append({'source': name, 'destination': f'res://{(DEST / filename).as_posix()}',
                       'sha256': name_hash, 'loop_requested': name in loops})
    destinations = {t['destination'] for t in tracks}
    if len(destinations) != len(tracks):
        raise ValueError('destination collision')
    by_source = {t['source']: t['destination'] for t in tracks}
    report = {'schema': 'mgsf.sound_identity.v0.2', 'archive_sha256': archive_sha,
              'technical_status': status, 'flags': sorted(set(flags)), 'files': records,
              'tracks': tracks, 'scene_tracks': {s: by_source[n] for s, n in scenes.items()},
              'promotion_gate': 'HOLD', 'evidence_class': 'offline_export_inspection',
              'applied': False, 'project_modified': False,
              'limits': ['No AMIX format guarantee, MIDI decoding, scene edits, or automatic import settings.',
                         'Loop and clipping tests are waveform heuristics; human listening is required.',
                         'Production promotion requires live game evidence and license confirmation.']}
    return report, payloads


def run_sound_identity(source: str | Path, project: str | Path, output: str | Path,
                       scene_map: str | Path | None = None, *, apply: bool = False,
                       allow_review: bool = False) -> dict:
    """Create a reviewable report; only --apply copies non-HOLD audio to Godot."""
    project, output = Path(project), Path(output)
    report, payloads = analyze_package(source, project, scene_map)
    if apply:
        if report['technical_status'] == 'HOLD':
            raise ValueError('HOLD: unsafe WAV; project not modified')
        if report['technical_status'] == 'REVIEW' and not allow_review:
            raise ValueError('REVIEW: pass --allow-review only after listening')
        paths = [(t, _target_ok(project, Path(t['destination'][6:]))) for t in report['tracks']]
        manifest = project / DEST / 'sound_map.json'
        _target_ok(project, DEST / 'sound_map.json')
        created = []
        try:
            for t, dest in paths:
                dest.parent.mkdir(parents=True, exist_ok=True)
                # No overwrite; symlink-in-path is checked again immediately before opening.
                _target_ok(project, dest.relative_to(project))
                with os.fdopen(os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o644), 'wb') as f:
                    created.append(dest)
                    f.write(payloads[t['source']])
            _target_ok(project, manifest.relative_to(project))
            with os.fdopen(os.open(manifest, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o644), 'w', encoding='utf-8') as f:
                created.append(manifest)
                json.dump({'schema': 'mgsf.sound_identity.godot_map.v0.2',
                           'tracks': report['tracks'], 'scene_tracks': report['scene_tracks'],
                           'loop_import_settings_required': True}, f, indent=2)
                f.write('\n')
        except BaseException:
            for file in reversed(created):
                file.unlink(missing_ok=True)
            raise
        report['applied'] = report['project_modified'] = True
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report
