"""Project-owned, repeatable projection of Obsidian notes and explicit ontology."""
import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import quote, unquote

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCOPE = 'stock-investing-ontology'


def dumps(value):
    return json.dumps(value, ensure_ascii=False, default=str)


def properties(data):
    # Neo4j properties cannot hold nested maps or mixed arrays.
    return {str(k): (v.isoformat() if isinstance(v, (date, datetime)) else
                    v if isinstance(v, (str, int, float, bool)) else dumps(v))
            for k, v in data.items() if v is not None}


def build_graph(vault):
    nodes, edges, warnings = {}, {}, []
    lookup = defaultdict(list)

    def node(identifier, label, props):
        props = {('original_' + key if key in {'id', 'scope', 'active', 'sync_run'} else key): value
                 for key, value in props.items()}
        nodes[identifier] = {'id': identifier, 'label': label, 'props': props}

    def edge(source, target, kind, props=None, key=''):
        identifier = hashlib.sha256(dumps([source, target, kind, key]).encode()).hexdigest()
        safe_props = {('original_' + k if k in {'id', 'sync_owner', 'sync_run'} else k): v
                      for k, v in (props or {}).items()}
        edges[identifier] = {'id': identifier, 'source': source, 'target': target,
                             'kind': kind, 'props': safe_props}

    files = sorted(vault.rglob('*.md'))
    for path in files:
        relative = path.relative_to(vault).as_posix()
        content = path.read_text(encoding='utf-8-sig')
        match = re.match(r'^---\s*\n(.*?)\n---(?:\n|$)', content, re.S)
        metadata = yaml.safe_load(match[1]) if match else {}
        if metadata is None:
            metadata = {}
        if not isinstance(metadata, dict):
            raise ValueError(f'Invalid frontmatter: {relative}')
        node('note:' + relative, 'Note', {
            **properties(metadata), 'title': path.stem, 'path': relative,
            'domain': relative.split('/')[0] if '/' in relative else '공통',
            'archived': relative.startswith('자료실/기존 혼합 기록/'),
            'content': content, 'frontmatter_json': dumps(metadata),
            'obsidian_uri': 'obsidian://open?path=' + quote(str(path.resolve())),
        })
        lookup[path.stem].append(relative)

    for path in sorted(vault.rglob('*')):
        if path.is_file() and path.suffix in {'.json', '.canvas', '.jpg', '.png', '.pdf'}:
            relative = path.relative_to(vault).as_posix()
            payload = path.read_bytes()
            props = {'title': path.name, 'path': relative, 'size_bytes': len(payload),
                     'sha256': hashlib.sha256(payload).hexdigest()}
            try:
                props['content'] = payload.decode('utf-8-sig')
                props['encoding'] = 'utf-8'
            except UnicodeDecodeError:
                props['encoding'] = 'non-utf8; original file retained'
            node('artifact:' + relative, 'Artifact', props)

    def resolve(target, source_path=None):
        target = unquote(target).replace('\\', '/').split('#')[0].split('^')[0].strip()
        if not target:
            return 'note:' + source_path if source_path else None
        if not Path(target).suffix or Path(target).suffix not in {'.md', '.json', '.canvas', '.pdf', '.png', '.jpg'}:
            target += '.md'
        candidates = [target]
        if source_path:
            candidates.insert(0, (Path(source_path).parent / target).as_posix())
        for candidate in candidates:
            # Normalize relative ../ references without allowing paths outside vault.
            resolved = (vault / candidate).resolve()
            if not resolved.is_relative_to(vault.resolve()):
                continue
            rel = resolved.relative_to(vault.resolve()).as_posix()
            if 'note:' + rel in nodes:
                return 'note:' + rel
            if 'artifact:' + rel in nodes:
                return 'artifact:' + rel
        matches = lookup[Path(target).stem]
        if len(matches) == 1:
            return 'note:' + matches[0]
        missing = 'missing:' + target
        node(missing, 'MissingReference', {'title': target.removesuffix('.md'),
                                         'path': target, 'reason': 'ambiguous' if matches else 'missing'})
        warnings.append({'source': source_path, 'target': target, 'candidates': matches})
        return missing

    for path in files:
        rel = path.relative_to(vault).as_posix()
        content = re.sub(r'```.*?```|~~~.*?~~~', '', nodes['note:' + rel]['props']['content'], flags=re.S)
        for match in re.finditer(r'\[\[([^\]]+)\]\]', content):
            raw = match[1].split('|')[0].rstrip('\\')
            target = resolve(raw, rel)
            if target:
                edge('note:' + rel, target, 'LINKS_TO', {'relation': '문서에서_참조한다'})
        for match in re.finditer(r'(?<!!)\[[^\]]+\]\(([^)]+)\)', content):
            raw = match[1].strip('<>')
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', raw) or not raw.split('#')[0].lower().endswith('.md'):
                continue
            edge('note:' + rel, resolve(raw, rel), 'LINKS_TO', {'relation': '문서에서_참조한다'})

    for path in sorted(vault.rglob('ontology.json')):
        rel = path.relative_to(vault).as_posix()
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        dataset = 'dataset:' + rel
        node(dataset, 'Dataset', {'title': rel, 'path': rel, 'data_json': dumps(data),
                                  'schema_version': str(data.get('schema_version', ''))})
        identifiers = set()
        for item in data.get('nodes', []):
            if item['id'] in identifiers:
                raise ValueError(f'Duplicate entity ID: {rel}: {item["id"]}')
            identifiers.add(item['id'])
            identifier = 'entity:' + rel + ':' + item['id']
            node(identifier, 'Entity', {**properties(item), 'entity_id': item['id'],
                                        'title': item.get('name', item.get('summary', item['id'])),
                                        'source_file': rel})
            edge(dataset, identifier, 'CONTAINS')
            if item.get('note'):
                edge(identifier, resolve(item['note']), 'DOCUMENTED_IN')
        for index, item in enumerate(data.get('edges', [])):
            if item['from'] not in identifiers or item['to'] not in identifiers:
                raise ValueError(f'Unknown ontology endpoint: {rel}: {item}')
            relation = item['relation']
            # Escape names safely; preserve Korean relationship names verbatim.
            edge('entity:' + rel + ':' + item['from'], 'entity:' + rel + ':' + item['to'],
                 relation, {**properties(item), 'source_file': rel, 'explicit': True}, str(index))
    return list(nodes.values()), list(edges.values()), warnings


def sync(driver, database, nodes, edges):
    run_id = datetime.now(timezone.utc).isoformat()
    with driver.session(database=database) as session:
        session.run('CREATE CONSTRAINT investment_graph_id IF NOT EXISTS FOR (n:GraphNode) REQUIRE (n.scope, n.id) IS UNIQUE').consume()

        def write(tx):
            tx.run('MATCH (n:GraphNode {scope:$scope}) SET n.active=false', scope=SCOPE).consume()
            for label in sorted({n['label'] for n in nodes}):
                rows = [n for n in nodes if n['label'] == label]
                tx.run(f'UNWIND $rows AS row MERGE (n:GraphNode {{scope:$scope, id:row.id}}) '
                       f'SET n = row.props, n.scope=$scope, n.id=row.id, n.active=true, n.sync_run=$run '
                       f'SET n:`{label}`', rows=rows, scope=SCOPE, run=run_id).consume()
            by_kind = defaultdict(list)
            for e in edges:
                by_kind[e['kind']].append(e)
            for kind, rows in by_kind.items():
                safe_kind = kind.replace('`', '``')
                tx.run('UNWIND $rows AS row MATCH (a:GraphNode {scope:$scope, id:row.source}) '
                       'MATCH (b:GraphNode {scope:$scope, id:row.target}) '
                       f'MERGE (a)-[r:`{safe_kind}` {{sync_owner:$scope, id:row.id}}]->(b) '
                       'SET r = row.props, r.sync_owner=$scope, r.id=row.id, r.sync_run=$run',
                       rows=rows, scope=SCOPE, run=run_id).consume()
            tx.run('MATCH ()-[r]->() WHERE r.sync_owner=$scope AND r.sync_run<>$run DELETE r',
                   scope=SCOPE, run=run_id).consume()
        session.execute_write(write)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--vault', type=Path, default=ROOT / 'obsidian-vault')
    parser.add_argument('--config', type=Path, default=ROOT / 'neo4j' / 'local.json')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    nodes, edges, warnings = build_graph(args.vault)
    report = {'nodes': len(nodes), 'relationships': len(edges),
              'labels': dict(Counter(n['label'] for n in nodes)), 'unresolved_links': warnings}
    if not args.dry_run:
        from neo4j import GraphDatabase
        config = json.loads(args.config.read_text(encoding='utf-8'))
        with GraphDatabase.driver(config['uri'], auth=(config['user'], config['password'])) as driver:
            driver.verify_connectivity()
            sync(driver, config.get('database', 'neo4j'), nodes, edges)
    report_dir = ROOT / 'reports' / 'neo4j'
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / 'sync-report.json').write_text(dumps(report), encoding='utf-8')
    print(dumps({k: v for k, v in report.items() if k != 'unresolved_links'}))
    print(f'Unresolved links: {len(warnings)}; details: reports/neo4j/sync-report.json')


if __name__ == '__main__':
    main()
