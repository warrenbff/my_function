// 시작하기: 이 문서의 링크를 그래프로 보기
MATCH (n:Note {scope:'stock-investing-ontology', title:'00. 시작하기', active:true})
MATCH p=(n)-[:LINKS_TO]->(m)
RETURN p LIMIT 80;

// 명시된 의미 관계만 보기 (원칙 채택 상태는 원본에 기록된 값 그대로)
MATCH p=(a:Entity {scope:'stock-investing-ontology', active:true})-[r]->(b:Entity)
WHERE r.explicit=true
RETURN p LIMIT 150;

// 플루언스 관련 기록 탐색
MATCH (n:Note {scope:'stock-investing-ontology', active:true})
WHERE n.title CONTAINS '플루언스' OR n.title CONTAINS 'FLNC'
OPTIONAL MATCH p=(n)-[:LINKS_TO]->(m)
RETURN n,p LIMIT 100;

// 성상현 원칙과 원문 출처 연결
MATCH p=(a:Entity {scope:'stock-investing-ontology', active:true})-[r]->(b:Entity)
WHERE a.entity_id STARTS WITH 'SSH-C' AND r.relation='출처가_있다'
RETURN p;

// 문서 유형별 현황
MATCH (n:Note {scope:'stock-investing-ontology', active:true})
RETURN n.type AS type, count(*) AS count ORDER BY count DESC;

// 연결이 끊겼거나 동명이어서 확정하지 못한 참조
MATCH (n:MissingReference {scope:'stock-investing-ontology', active:true})
RETURN n.title,n.reason;
