야광충 2 (Nintendo 64) 일본어판용 한글패치 v1.2입니다.

- 원본에서 BPS 적용 및 소스 재빌드 결과가 최종 ROM과 정확히 일치합니다.
- 2026-10-14에 주요 화면과 후반 진행을 추가 검수했습니다. 범위와 결과는 QA_REPORT.md를 참고하세요.
- ZIP에는 차분 패치와 적용 도구·안내문만 포함합니다. ROM·개인 저장·개발 로그는 제외했습니다.
- 원본 SHA-256: `c6a52c2377f3d6236ba2d29557461b9af106d99afeba2156e21e2477b00ddffd`
- 결과 SHA-256: `2109f2fdd80e31d6e894b2d64fc4bb748eb73b7ef311a64b28d66025b9263fa1`

ZIP을 풀고 Python 3로 다음 명령을 실행하세요.

```text
python -X utf8 -B reproduce/apply_verified_patch.py ORIGINAL.z64 --output Yakouchuu_II_KO_v1.2.z64
```

이전 패치의 세이브스테이트는 재사용하지 마세요. 실제 N64 하드웨어와 모든 분기의 재완주는 미검증입니다.
