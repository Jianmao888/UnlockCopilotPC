"""Plan, validate or assemble pinned offline product files. Never installs."""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from product_layout import definition, materialize, validate_content

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--product', required=True)
mode = parser.add_mutually_exclusive_group(required=True)
mode.add_argument('--plan', action='store_true')
mode.add_argument('--validate', type=pathlib.Path, metavar='CONTENT_DIRECTORY')
mode.add_argument('--output', type=pathlib.Path, metavar='NEW_CONTENT_DIRECTORY')
parser.add_argument('--engine', type=pathlib.Path)
parser.add_argument('--rum', type=pathlib.Path)
parser.add_argument('--payload-dir', action='append', type=pathlib.Path)
args = parser.parse_args()
try:
    if args.plan:
        result = dict(product=args.product, canonicalPayloads=definition(args.product), installCalled=False)
    elif args.validate:
        result = validate_content(args.validate, args.product)
    else:
        if not args.engine or not args.rum or not args.payload_dir:
            parser.error('--output requires --engine, --rum and --payload-dir')
        result = materialize(args.output, args.product, args.engine, args.rum, args.payload_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
except (OSError, ValueError, KeyError) as error:
    parser.exit(1, 'Content preparation failed: ' + str(error) + '\n')
