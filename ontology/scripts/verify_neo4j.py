"""Read-only check of imported data and the supplied Browser queries."""
import json
from neo4j import GraphDatabase
from sync_neo4j import ROOT, SCOPE, build_graph


def main():
    expected_nodes, expected_edges, _ = build_graph(ROOT / 'obsidian-vault')
    config = json.loads((ROOT / 'neo4j/local.json').read_text(encoding='utf-8'))
    with GraphDatabase.driver(config['uri'], auth=(config['user'], config['password'])) as driver:
        with driver.session(database=config['database'], default_access_mode='READ') as session:
            actual_nodes = {r['id']: dict(r['node']) for r in session.run(
                'MATCH (n:GraphNode {scope:$scope,active:true}) RETURN n.id AS id,n AS node', scope=SCOPE)}
            assert set(actual_nodes) == {n['id'] for n in expected_nodes}, 'Node IDs differ'
            for node in expected_nodes:
                for key, value in node['props'].items():
                    assert actual_nodes[node['id']][key] == value, (node['id'], key)
            actual_edges = {r['id']: (r['source'], r['target'], r['kind'], dict(r['edge'])) for r in session.run(
                'MATCH (a)-[r]->(b) WHERE r.sync_owner=$scope '
                'RETURN r.id AS id,a.id AS source,b.id AS target,type(r) AS kind,r AS edge', scope=SCOPE)}
            assert set(actual_edges) == {e['id'] for e in expected_edges}, 'Relationship IDs differ'
            for edge in expected_edges:
                source, target, kind, props = actual_edges[edge['id']]
                assert (source, target, kind) == (edge['source'], edge['target'], edge['kind'])
                for key, value in edge['props'].items():
                    assert props[key] == value, (edge['id'], key)
            queries = (ROOT / 'neo4j/queries.cypher').read_text(encoding='utf-8').split(';')
            results = []
            for query in queries:
                if query.strip():
                    results.append(len(list(session.run(query))))
    print(json.dumps({'verified_nodes': len(actual_nodes), 'verified_relationships': len(actual_edges),
                      'example_query_results': results}))


if __name__ == '__main__':
    main()
