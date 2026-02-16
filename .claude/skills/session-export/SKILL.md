---
name: session-export
description: Claude Code 세션 대화 내역을 마크다운으로 export. 트리거 - "세션 내보내기", "세션 export", "대화 내역 추출", "session export", "대화 기록 저장", "오늘 대화 정리", "세션 마크다운", "JSONL 파싱", "대화 로그"
---

# Session Export

Claude Code 세션 JSONL 파일을 파싱하여 읽기 좋은 마크다운으로 변환한다.

## 사용법

`scripts/export_sessions.py` 스크립트를 실행한다. 현재 작업 디렉토리(cwd)를 기반으로 프로젝트 디렉토리를 자동 감지한다.

```bash
# 기본: 현재 프로젝트의 모든 세션을 ./sessions/ 에 export
python3 <skill-dir>/scripts/export_sessions.py --output-dir ./sessions

# 현재 세션 제외
python3 <skill-dir>/scripts/export_sessions.py --output-dir ./day1 --current-session <SESSION_ID>

# 특정 세션만 export
python3 <skill-dir>/scripts/export_sessions.py --session a34203b1 --output-dir ./out

# 디버그 출력
python3 <skill-dir>/scripts/export_sessions.py -v
```

## 옵션

| 옵션 | 설명 |
|------|------|
| `--project-dir PATH` | Claude 프로젝트 디렉토리 (미지정 시 cwd 기반 자동 감지) |
| `--output-dir PATH` | 출력 디렉토리 (기본: `./sessions`) |
| `--current-session ID` | 제외할 현재 세션 ID |
| `--session ID` | 특정 세션만 export (부분 매치 가능) |
| `--verbose`, `-v` | 디버그 출력 |

## 출력 형식

세션당 하나의 마크다운 파일 (`chatsession-{번호}-{topic}.md`). topic은 첫 사용자 메시지에서 영문 단어를 추출하여 자동 생성 (alphabet+hyphen). 중복 시 `-2`, `-3` 접미사 추가:
- 헤더: 세션 ID, 시작 시각(KST), 메시지 수
- 메시지: User/Assistant 구분, 타임스탬프 포함
- 도구 호출은 `[Tool: 이름 → 대상]` 형태로 요약
- system-reminder 등 시스템 태그 자동 제거
- sidechain 메시지 제외

## 워크플로우

1. 사용자가 세션 export를 요청하면 이 스킬이 트리거된다
2. 현재 cwd에서 프로젝트 디렉토리를 감지한다 (`~/.claude/projects/` 내)
3. `export_sessions.py`를 적절한 옵션과 함께 실행한다
4. 결과 파일 목록을 사용자에게 보여준다
