"""Explicit file-only recovery bundle. Never uploads, installs or restores Windows.

Export deduplicates by SHA256. Restore writes into a NEW ordinary directory only.
The bundle does not preserve ACLs or constitute a bootable/system image backup.
"""
import argparse
import hashlib
import json
import pathlib
import shutil


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe_relative(value):
    path = pathlib.PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or ':' in value or '\\' in value:
        raise ValueError('Unsafe relative path in bundle')
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument('--plan', action='store_true')
    operation.add_argument('--export', action='store_true')
    operation.add_argument('--verify', action='store_true')
    operation.add_argument('--restore', action='store_true')
    parser.add_argument('--source', action='append', default=[], metavar='LABEL=FILE_OR_DIRECTORY')
    parser.add_argument('--sources-json', type=pathlib.Path, help='Explicit JSON object mapping simple labels to local source paths')
    parser.add_argument('--bundle', required=True, type=pathlib.Path)
    parser.add_argument('--destination', type=pathlib.Path)
    args = parser.parse_args()
    bundle = args.bundle.resolve()
    if args.plan or args.export:
        records, labels = [], set()
        if args.sources_json:
            mapping = json.loads(args.sources_json.read_text(encoding='utf-8-sig'))
            if not isinstance(mapping, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in mapping.items()):
                raise ValueError('sources-json must be an object of label: path strings')
            args.source.extend(label + '=' + value for label, value in mapping.items())
        for specification in args.source:
            label, source_name = specification.split('=', 1)
            if not label or not all(c.isalnum() or c in '-_' for c in label) or label in labels:
                raise ValueError('Each source requires a unique simple label')
            labels.add(label)
            source = pathlib.Path(source_name).resolve(strict=True)
            if bundle == source or bundle.is_relative_to(source):
                raise ValueError('Bundle must be outside every source')
            files = [source] if source.is_file() else sorted(source.rglob('*'))
            for path in files:
                if not path.is_file() or '.git' in path.parts or '__pycache__' in path.parts:
                    continue
                resolved = path.resolve(strict=True)
                if source.is_dir() and not resolved.is_relative_to(source):
                    raise ValueError('Source link escapes its explicitly selected directory')
                relative = path.name if source.is_file() else path.relative_to(source).as_posix()
                safe_relative(relative)
                records.append(dict(label=label, relative=relative, source=str(resolved), bytes=path.stat().st_size))
        if not records:
            raise ValueError('No source files selected')
        if args.plan:
            print(json.dumps(dict(files=len(records), upperBoundBytes=sum(r['bytes'] for r in records),
                                  bundle=str(bundle), written=False), indent=2))
            return
        if bundle.exists():
            raise ValueError('Export requires a new bundle directory')
        bundle.mkdir(parents=True)
        manifest = dict(schema=1, complete=False, files=records, systemImage=False, preservesAcl=False)
        manifest_path = bundle / 'manifest.json'
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        for row in records:
            source = pathlib.Path(row['source'])
            sha = digest(source)
            obj = bundle / 'objects' / sha[:2] / sha
            if not obj.exists():
                obj.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, obj)
            if obj.stat().st_size != row['bytes'] or digest(obj) != sha or digest(source) != sha:
                raise ValueError('Source changed or copy failed; bundle remains marked incomplete')
            row['sha256'] = sha
        manifest['complete'] = True
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        print('Bundle exported. Copy it off this computer and run --verify there:', bundle)
        return
    manifest = json.loads((bundle / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('schema') != 1 or manifest.get('complete') is not True:
        raise ValueError('Bundle is incomplete or unsupported')
    checked = set()
    for row in manifest['files']:
        safe_relative(row['relative'])
        safe_relative(row['label'])
        sha = row['sha256']
        if len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha):
            raise ValueError('Invalid object hash')
        obj = bundle / 'objects' / sha[:2] / sha
        if sha not in checked and (obj.stat().st_size != row['bytes'] or digest(obj) != sha):
            raise ValueError('Missing/corrupt bundle object: ' + sha)
        checked.add(sha)
    if args.restore:
        if not args.destination or args.destination.exists():
            raise ValueError('Restore requires a NEW --destination directory')
        destination = args.destination.resolve()
        destination.mkdir(parents=True)
        for row in manifest['files']:
            target = destination / row['label'] / row['relative']
            if not target.resolve().is_relative_to(destination):
                raise ValueError('Restore target escapes destination')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bundle / 'objects' / row['sha256'][:2] / row['sha256'], target)
    print(json.dumps(dict(verified=True, files=len(manifest['files']), uniqueObjects=len(checked),
                          restored=args.restore, systemFilesInstalled=False), indent=2))


if __name__ == '__main__':
    main()
