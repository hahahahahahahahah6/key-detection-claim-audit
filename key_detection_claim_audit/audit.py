"""Offline documentation and single-module syntax inspection."""
import argparse
import ast
import json
import os
from pathlib import Path
import re
import sys

from . import __version__
from .phrases import KEY, NOKEY

GENERIC = frozenset('''detect_key estimate_key get_key key_detect detect_musical_key estimate_musical_key get_musical_key musical_key_detect identify_key key_identify predict_key key_predict classify_key key_classify analyze_key analyse_key extract_key key_extract detect_tonality estimate_tonality get_tonality tonality_detect detect_key_signature estimate_key_signature detect_tonic estimate_tonic'''.split())


def normalize(text):
    return re.sub(r'\s+', ' ', text.lower().replace("n't", ' not').replace('-', ' ')).strip()


def claims(text):
    lines = []
    fence = None
    for line in text.splitlines():
        match = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line)
        if fence:
            if match and match[1][0] == fence[0] and len(match[1]) >= len(fence) and not match[2].strip():
                fence = None
            lines.append('')
        elif match:
            fence = match[1]
            lines.append('')
        else:
            lines.append(line)
    positive = negative = False
    for paragraph in re.split(r'\n\s*\n', '\n'.join(lines)):
        value = normalize(paragraph)
        for phrase in sorted(NOKEY, key=lambda x: (-len(x), x)):
            value, count = re.subn(r'\b' + re.escape(phrase) + r'\b', lambda m: ' ' * len(m[0]), value)
            negative |= bool(count)
        for phrase in sorted(KEY, key=lambda x: (-len(x), x)):
            if re.search(r'\b' + re.escape(phrase) + r'\b', value):
                positive = True
                value = re.sub(r'\b' + re.escape(phrase) + r'\b', lambda m: ' ' * len(m[0]), value)
    return positive, negative


def evidence(source):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    essentia = set()
    imported = {}
    shadow = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                if item.name == 'essentia' or item.name.startswith('essentia.'):
                    essentia.add(item.asname or item.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            for item in node.names:
                imported[item.asname or item.name] = item.name
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            shadow.add(node.name)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute):
            base = func.value
            while isinstance(base, ast.Attribute):
                base = base.value
            if func.attr == 'KeyExtractor' and isinstance(base, ast.Name) and base.id in essentia:
                return True
            if func.attr in GENERIC and func.attr not in shadow:
                return True
        elif isinstance(func, ast.Name):
            target = imported.get(func.id)
            if target in GENERIC and func.id not in shadow and target not in shadow:
                return True
    return False


def audit(root, ignore=()):
    root = Path(root)
    if not root.is_dir() or root.is_symlink():
        raise OSError('Root must be a readable directory')
    prefixes = [tuple(Path(x).parts) for x in ignore if x]
    docs, sources = [], []
    production = test = positive = negative = False
    def ignored(rel):
        return any(rel.parts[:len(prefix)] == prefix for prefix in prefixes)
    def failed(error):
        raise error
    for directory, dirs, files in os.walk(root, onerror=failed, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not (Path(directory)/d).is_symlink() and not ignored((Path(directory)/d).relative_to(root)))
        for name in sorted(files):
            path = Path(directory)/name
            rel = path.relative_to(root)
            if path.is_symlink() or ignored(rel):
                continue
            if rel.as_posix() == 'README.md' or (path.suffix == '.md' and 'docs' in rel.parts[:-1]):
                docs.append(rel.as_posix())
                yes, no = claims(path.read_text(encoding='utf-8'))
                positive |= yes
                negative |= no
            if path.suffix != '.py' or set(rel.parts[:-1]) & {'fixtures', 'docs', 'examples'}:
                continue
            sources.append(rel.as_posix())
            found = evidence(path.read_text(encoding='utf-8'))
            is_test = 'tests' in rel.parts[:-1] or name.startswith('test_') or name.endswith('_test.py')
            if is_test:
                test |= found
            else:
                production |= found
    findings = []
    if positive and not production:
        findings.append({'id': 'documented-key-detection-claim-false', 'severity': 'MEDIUM' if test else 'HIGH', 'message': 'Affirmative documentation lacks production evidence.'})
    if negative and production:
        findings.append({'id': 'documented-no-key-detection-claim-false', 'severity': 'HIGH', 'message': 'Negative documentation conflicts with production evidence.'})
    return dict(verdict='FAIL' if findings else 'PASS', findings=findings, documents=docs, sources=sources, production_evidence=production, test_evidence=test)


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(1, self.prog + ': error: ' + message + '\n')


def main(argv=None):
    parser = Parser(description=__doc__)
    parser.add_argument('root')
    parser.add_argument('--version', action='version', version=__version__)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--verbose', action='store_true')
    parser.add_argument('--ignore', action='append', default=[])
    parser.add_argument('--fail-on', choices=['LOW', 'MEDIUM', 'HIGH'], default='HIGH')
    args = parser.parse_args(argv)
    try:
        result = audit(args.root, args.ignore)
    except (OSError, UnicodeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(result['verdict'])
        for finding in result['findings']:
            print('{id} {severity}: {message}'.format(**finding))
        if args.verbose:
            print(json.dumps(result, sort_keys=True))
    levels = {'LOW': 0, 'MEDIUM': 1, 'HIGH': 2}
    return 2 if any(levels[f['severity']] >= levels[args.fail_on] for f in result['findings']) else 0
