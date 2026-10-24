# 투자 온톨로지 — Neo4j 사용법

이 PC에는 Neo4j Community 5.26.30과 Java 21을 프로젝트 전용으로 설치했다. 데이터는 `stock-investing-skills/.cache/neo4j/`에 저장되고, 외부로 전송하지 않는다. 서버는 `127.0.0.1`에서만 접속할 수 있다.

## 접속

브라우저에서 <http://127.0.0.1:7474/browser/>를 연다.

- 연결 주소: `bolt://127.0.0.1:7687`
- 사용자: `neo4j`
- 비밀번호: 이 폴더의 `local.json`에 있는 `password` 값. 이 파일은 Git에서 제외했다.
- 데이터베이스: `neo4j`

`queries.cypher`의 쿼리를 하나씩 복사해 실행한다. 시작 화면의 문서 연결을 보려면:

```cypher
MATCH p=(n:Note {scope:'stock-investing-ontology', title:'00. 시작하기', active:true})-[:LINKS_TO]->(m)
RETURN p LIMIT 80;
```

결과의 Graph 탭에서 노드를 누르면 본문, 유형, 검증 상태 등을 확인할 수 있다. Note 노드의 `obsidian_uri`는 원본 문서를 여는 주소다. Browser의 그래프 스타일에서 Note/Entity의 caption을 `title`로 지정하면 한글 제목을 표시할 수 있다.

## PC를 재시작한 뒤

프로젝트 폴더에서 PowerShell로 실행한다. 서버가 시작되는 데 약 30~60초가 걸릴 수 있다. 자동 시작은 등록하지 않았다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File neo4j/start.ps1
```

## Obsidian 문서를 수정한 뒤

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File neo4j/sync.ps1
```

원본은 Obsidian Markdown과 `ontology.json`이다. 동기화는 원본에서 Neo4j로 진행된다. Neo4j에서 직접 수정한 가져오기 속성은 다음 동기화 때 원본 값으로 갱신된다. 삭제된 원본 노드는 `active=false`로 보관하고, 더 이상 존재하지 않는 가져오기 관계는 제거한다. 직접 추가한 관계는 `sync_owner`를 설정하지 않으면 동기화에서 건드리지 않는다.

## 그래프 의미

| 표시 | 의미 |
| --- | --- |
| `Note` | Markdown 문서. 본문·frontmatter·폴더 영역·보존 자료 여부를 유지 |
| `Entity` | `ontology.json`에 명시된 엔터티 52개. 원본 식별자는 `entity_id` |
| `Dataset` | 원본 온톨로지 JSON 전체. 추가 분석·채택 이벤트도 `data_json`에 보존 |
| `Artifact` | JSON·Canvas 파일 참조. UTF-8 파일은 본문도 보존하고 다른 인코딩은 경로·해시로 연결 |
| `MissingReference` | 없는 대상 또는 동명이어서 확정할 수 없는 문서 링크 |
| `LINKS_TO` | 문서 탐색 링크. 근거·채택·인과관계를 뜻하지 않음 |
| `DOCUMENTED_IN` | 명시 엔터티와 설명 문서의 연결 |
| 한글 관계명 | JSON에 명시된 의미 관계. `explicit=true`, 출처·페이지·기타 속성 보존 |

스키마 문서의 관계 표와 복기 본문을 해석해 새로운 사실 관계를 자동 확정하지 않는다. 외부 원칙의 `adoption_status`, 판단의 검증 상태도 원본 그대로 유지한다. Neo4j에서 새 의미 관계를 관리하려면 먼저 원본 JSON에 기록한 뒤 동기화한다.

링크 점검 결과는 `reports/neo4j/sync-report.json`에 저장된다. 원본의 연결이 없는 링크·템플릿 자리표시자·동명 문서는 임의로 연결하지 않는다.

## 설치 재현 및 확인

Python 3.12와 인터넷 연결이 있으면 다음으로 설치를 재현한다. 다운로드는 배포처의 SHA-256과 비교하고 Python 패키지는 별도 가상환경에 설치한다.

```powershell
python scripts/setup_neo4j.py
powershell -NoProfile -ExecutionPolicy Bypass -File neo4j/start.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File neo4j/sync.ps1
& .cache/neo4j-venv/Scripts/python.exe scripts/verify_neo4j.py
```

Windows 실행기의 한글 경로 문제를 피하기 위해 `%LOCALAPPDATA%/InvestmentOntologyNeo4j`가 프로젝트의 `.cache/neo4j`를 가리킨다. 프로젝트를 옮길 경우 이 연결 경로도 갱신해야 한다. `.cache/neo4j`와 `neo4j/local.json`을 보관하면 데이터와 로그인 정보를 유지할 수 있다.

오류가 나면 `.cache/neo4j/console.log`, `console-error.log`, Neo4j의 `logs/`를 확인한다. 기본 포트가 다른 프로그램에서 사용 중이면 기존 서비스를 확인한 뒤 포트 설정을 변경해야 한다.

구성 참고: [Neo4j Windows 설치](https://neo4j.com/docs/operations-manual/current/installation/windows/), [Java 호환 요구사항](https://neo4j.com/docs/operations-manual/5/installation/requirements/), [공식 Python 드라이버](https://neo4j.com/docs/python-manual/current/).
