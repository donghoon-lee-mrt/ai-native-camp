---
name: transcript-correction
description: Google Meet 녹화 트랜스크립트 HTML을 SRT로 변환하고 STT 오타를 보정한다. 트리거 - "트랜스크립트 보정", "transcript correction", "STT 보정", "자막 보정", "SRT 변환", "녹화 트랜스크립트", "오타 보정"
---

# Transcript Correction

Google Meet 녹화 트랜스크립트 HTML 파일을 SRT로 변환하고, 음성 인식(STT) 오류를 AI로 보정하는 파이프라인.

## 파일 컨벤션

```
{name}.transcript.txt.html    # 입력: Google Meet 트랜스크립트 HTML
{name}.transcript.srt          # 중간: SRT 변환 결과
{name}.transcript.corrected.srt # 출력: 오타 보정된 최종 SRT
```

파이프라인 완료 후 입력/중간 파일은 `.` 접두사로 숨김 처리:
```
.{name}.transcript.txt.html   # 숨김
.{name}.transcript.srt         # 숨김
{name}.transcript.corrected.srt # 최종 결과만 노출
```

## 워크플로우

사용자가 HTML 파일 경로를 제공하면 아래 3단계를 **Task로 감싸서** 실행한다.

### Step 1: HTML → SRT 변환

```bash
python3 <skill-dir>/scripts/html_to_srt.py <input.html> [--verbose]
```

출력 파일명은 자동 결정: `{name}.transcript.txt.html` → `{name}.transcript.srt`

변환 후 검증:
- 엔트리 수가 0이 아닌지 확인
- 시퀀스 번호 연속성 확인

### Step 2: SRT 오타 보정 (병렬)

SRT를 6개 청크로 분할하여 병렬 보정한다.

#### 2-1. 청크 분할

```python
import re

with open(srt_path, 'r') as f:
    content = f.read()

entries = re.split(r'\n\n+', content.strip())
total = len(entries)
chunk_size = (total + 5) // 6

for i in range(6):
    start = i * chunk_size
    end = min((i + 1) * chunk_size, total)
    chunk = '\n\n'.join(entries[start:end]) + '\n'
    with open(f'/tmp/srt_correction/chunk_{i+1}.srt', 'w') as f:
        f.write(chunk)
```

#### 2-2. 병렬 보정 에이전트 실행

6개 Task 에이전트를 **background로 동시 실행**한다. 각 에이전트에 아래 프롬프트를 전달:

```
You are correcting Korean speech-to-text transcription errors in an SRT subtitle file
from an AI Native Workshop.

Read /tmp/srt_correction/chunk_{N}.srt and correct transcription errors.

**Common transcription errors to fix:**
- "클러드"/"클라드"/"크로드"/"클럽"/"클럽드"/"프로드" → "클로드" (Claude)
- "클럽 MD"/"클러엔디"/"클러뎀" → "CLAUDE.MD"
- "서브에트"/"서브웨이전트"/"서베이전트" → "서브 에이전트"
- "고스티"/"고스트" → "Ghostty"
- "안티그래프티"/"안테그리티" → "Windsurf"
- "스 코드"/"스스포드" → "VS Code"
- "채티피티"/"최피pt"/"채피트" → "ChatGPT"
- "프롬트"/"프트" → "프롬프트"
- "테스크" → "태스크"
- "슬렉"/"슬랭" → "슬랙"
- "기터브"/"깃업"/"기업" → "깃허브"
- "블락"/"블럭" → "블록"
- "스킵" (skill context) → "스킬"
- "코파일러" → "코파일럿"
- "아이디이" (editor) → "IDE"
- "에니전트"/"에이션트" → "에이전트"
- "플러인"/"플러이"/"클러그인" → "플러그인"
- "오보딩"/"언버딩" → "온보딩"
- "리니언" → "리니어" (Linear)
- "소매스" → "소네트" (Sonnet)
- "하이코" → "하이쿠" (Haiku)
- "MGP" → "MCP"
- "엔트로피" → "앤트로픽" (Anthropic)
- "사스" → "SaaS"
- "해계모니" → "헤게모니"
- "쓰레" → "스레드"
- "CNI" → "CLI"

**Rules:**
1. Only fix clear transcription errors. Don't rewrite sentences.
2. Preserve SRT format exactly (sequence numbers, timestamps, blank lines).
3. Keep speaker labels as-is.
4. For heavily garbled sections (break chatter), leave mostly as-is.

Write corrected output to /tmp/srt_correction/chunk_{N}_corrected.srt
```

**중요**: 워크숍 컨텍스트가 다를 경우, 사용자에게 추가 컨텍스트를 물어보고 프롬프트에 반영할 것.

#### 2-3. 보정 청크 병합

모든 에이전트 완료 후:

```python
import re

chunks = []
for i in range(1, 7):
    with open(f'/tmp/srt_correction/chunk_{i}_corrected.srt') as f:
        chunks.append(f.read().strip())

merged = '\n\n'.join(chunks) + '\n'

with open(corrected_path, 'w') as f:
    f.write(merged)

# 정합성 검증
entries = re.split(r'\n\n+', merged.strip())
nums = [int(e.split('\n')[0]) for e in entries]
expected = list(range(1, len(nums) + 1))
assert nums == expected, f"Sequence error: missing={set(expected)-set(nums)}"
print(f"OK: {len(entries)} entries merged")
```

### Step 3: 정리

파이프라인 완료 후 중간 파일을 숨김 처리:

```bash
# 원본 HTML 숨기기
mv {name}.transcript.txt.html .{name}.transcript.txt.html

# 중간 SRT 숨기기
mv {name}.transcript.srt .{name}.transcript.srt

# 임시 청크 삭제
rm -rf /tmp/srt_correction/
```

최종 상태:
```
.{name}.transcript.txt.html     # 숨김
.{name}.transcript.srt           # 숨김
{name}.transcript.corrected.srt  # 최종 결과
```

## 실행 예시

```
사용자: "day3.transcript.txt.html 트랜스크립트 보정해 줘"

1. Task: html_to_srt.py 실행 → day3.transcript.srt 생성
2. Task x6: 청크 분할 + 병렬 보정 → chunk_1~6_corrected.srt
3. 병합 → day3.transcript.corrected.srt
4. 숨김 처리 → .day3.transcript.txt.html, .day3.transcript.srt
```
