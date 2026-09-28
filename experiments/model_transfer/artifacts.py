"""Restore a same-repository Actions artefact after checking its archive paths."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tempfile
from zipfile import ZipFile


def extract_archive(archive: Path, destination: Path) -> None:
    if destination.exists():
        raise ValueError('Restore into a new output directory')
    with ZipFile(archive) as bundle:
        members = bundle.infolist()
        if sum(m.file_size for m in members) > 2 * 1024 ** 3:
            raise ValueError('Artefact exceeds the 2 GiB extraction limit')
        seen = set()
        for member in members:
            path = PurePosixPath(member.filename)
            if (path.is_absolute() or '..' in path.parts or '\\' in member.filename or
                    stat.S_ISLNK(member.external_attr >> 16) or str(path) in seen):
                raise ValueError('Unsafe or duplicate artefact path')
            seen.add(str(path))
        destination.mkdir(parents=True)
        bundle.extractall(destination)
    if not (destination / 'plan.json').is_file():
        raise ValueError('Artefact must contain a run with plan.json at its root')


def restore(repository: str, artifact_id: str, destination: Path) -> dict:
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository) or not re.fullmatch(r'[1-9][0-9]*', artifact_id):
        raise ValueError('A repository and numeric artefact ID are required')
    endpoint = f'repos/{repository}/actions/artifacts/{artifact_id}'
    metadata = json.loads(subprocess.check_output(['gh', 'api', endpoint], text=True))
    if metadata.get('expired'):
        raise ValueError('The selected artefact has expired')
    with tempfile.TemporaryDirectory() as directory:
        archive = Path(directory) / 'run.zip'
        with archive.open('wb') as stream:
            subprocess.run(['gh', 'api', endpoint + '/zip'], stdout=stream, check=True)
        expected = metadata.get('digest')
        actual = 'sha256:' + hashlib.sha256(archive.read_bytes()).hexdigest()
        if expected and expected != actual:
            raise ValueError('Downloaded artefact digest mismatch')
        extract_archive(archive, destination)
    return {'artifact_id': artifact_id, 'digest': actual, 'source_run': metadata.get('workflow_run')}
