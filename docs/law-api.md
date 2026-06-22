#1 : Endpoint 1

현행법령(시행일) 목록 조회 API
- 요청 URL : http://www.law.go.kr/DRF/lawSearch.do?target=eflaw
요청 변수 (request parameter)
요청변수	값	설명
OC	string(필수)	신청한 API인증값
target	string : eflaw(필수)	서비스 대상
type	char(필수)	출력 형태 HTML/XML/JSON
생략시 기본값: XML
search	int	검색범위 (기본 : 1 법령명) 2 : 본문검색
query	string	법령명에서 검색을 원하는 질의
(정확한 검색을 위한 문자열 검색 query="자동차")
nw	int	1: 연혁, 2: 시행예정, 3: 현행 (기본값: 전체)
연혁+예정 : nw=1,2
예정+현행 : nw=2,3
연혁+현행 : nw=1,3
연혁+예정+현행 : nw=1,2,3
LID	string	법령ID (LID=830)
display	int	검색된 결과 개수 (default=20 max=100)
page	int	검색 결과 페이지 (default=1)
sort	string	정렬옵션(기본 : lasc 법령오름차순)
ldes : 법령내림차순
dasc : 공포일자 오름차순
ddes : 공포일자 내림차순
nasc : 공포번호 오름차순
ndes : 공포번호 내림차순
efasc : 시행일자 오름차순
efdes : 시행일자 내림차순
efYd	string	시행일자 범위 검색(20090101~20090130)
date	string	공포일자 검색
ancYd	string	공포일자 범위 검색(20090101~20090130)
ancNo	string	공포번호 범위 검색(306~400)
rrClsCd	string	법령 제개정 종류
(300201-제정 / 300202-일부개정 / 300203-전부개정
300204-폐지 / 300205-폐지제정 / 300206-일괄개정
300207-일괄폐지 / 300209-타법개정 / 300210-타법폐지
300208-기타)
nb	int	법령의 공포번호 검색
org	string	소관부처별 검색(소관부처코드 제공)
knd	string	법령종류(코드제공)
gana	string	사전식 검색 (ga,na,da…,etc)
popYn	string	상세화면 팝업창 여부(팝업창으로 띄우고 싶을 때만 'popYn=Y')
샘플 URL
1. 시행일 법령 목록 XML 검색
http://www.law.go.kr/DRF/lawSearch.do?OC=test&target=eflaw&type=XML
2. 시행일 법령 목록 HTML 검색
http://www.law.go.kr/DRF/lawSearch.do?OC=test&target=eflaw&type=HTML
3. 시행일 법령 목록 JSON 검색
http://www.law.go.kr/DRF/lawSearch.do?OC=test&target=eflaw&type=JSON
4. 법령 검색 : 자동차관리법
http://www.law.go.kr/DRF/lawSearch.do?OC=test&target=eflaw&query=자동차관리법
5. 법령 공포일자 내림차순 검색
http://www.law.go.kr/DRF/lawSearch.do?OC=test&target=eflaw&type=XML&sort=ddes
6. 소관부처가 국토교통부인 법령 검색
http://www.law.go.kr/DRF/lawSearch.do?OC=test&target=eflaw&type=XML&org=1613000
7. '도서관법'을 법령 ID(830)로 검색
http://www.law.go.kr/DRF/lawSearch.do?OC=test&target=eflaw&type=XML&LID=830
출력 결과 필드(response field)
필드	값	설명
target	string	검색서비스 대상
키워드	string	검색어
section	string	검색범위
totalCnt	int	검색건수
page	int	결과페이지번호
law id	int	결과 번호
법령일련번호	int	법령일련번호
현행연혁코드	string	현행연혁코드
법령명한글	string	법령명한글
법령약칭명	string	법령약칭명
법령ID	int	법령ID
공포일자	int	공포일자
공포번호	int	공포번호
제개정구분명	string	제개정구분명
소관부처코드	string	소관부처명
소관부처명	string	소관부처명
법령구분명	string	법령구분명
공동부령구분	string	공동부령구분
공포번호	string	공포번호(공동부령의 공포번호)
시행일자	int	시행일자
자법타법여부	string	자법타법여부
법령상세링크	string	법령상세링크

#2 : EndPoint 2

현행법령(시행일) 본문 조회 API
- 요청 URL : http://www.law.go.kr/DRF/lawService.do?target=eflaw
요청 변수 (request parameter)
요청변수	값	설명
OC	string(필수)	신청한 API인증값
target	string : eflaw(필수)	서비스 대상
type	char(필수)	출력 형태 : HTML/XML/JSON
생략시 기본값 : XML
ID	char	법령 ID (ID 또는 MST 중 하나는 반드시 입력,
ID로 검색하면 그 법령의 현행 법령 본문 조회)
MST	char	법령 마스터 번호 - 법령테이블의 lsi_seq 값을 의미함
efYd	int(필수)	법령의 시행일자
(ID 입력시에는 무시하는 값으로 입력하지 않음)
JO	int	조번호
생략(기본값) : 모든 조를 표시함
6자리숫자 : 조번호(4자리)+조가지번호(2자리)
(000200 : 2조, 001002 : 10조의 2)
chrClsCd	char	원문/한글 여부
생략(기본값) : 한글
(010202 : 한글, 010201 : 원문)
샘플 URL
1. 자동차관리법 ID HTML 상세조회
http://www.law.go.kr/DRF/lawService.do?OC=test&target=eflaw&ID=1747&type=HTML
2. 자동차관리법 법령 Seq XML 조회
http://www.law.go.kr/DRF/lawService.do?OC=test&target=eflaw&MST=166520&efYd=20151007&type=XML
3. 자동차관리법 3조 XML 상세조회
http://www.law.go.kr/DRF/lawService.do?OC=test&target=eflaw&MST=166520&efYd=20151007&JO=000300&type=XML
4. 자동차관리법 ID JSON 상세조회
http://www.law.go.kr/DRF/lawService.do?OC=test&target=eflaw&ID=1747&type=JSON
출력 결과 필드(response field)
필드	값	설명
법령ID	int	법령ID
공포일자	int	공포일자
공포번호	int	공포번호
언어	string	언어종류
법종구분	string	법종류의 구분
법종구분코드	string	법종구분코드
법령명_한글	string	한글법령명
법령명_한자	string	법령명_한자
법령명약칭	string	법령명약칭
편장절관	int	편장절관 일련번호
소관부처코드	int	소관부처코드
소관부처	string	소관부처명
전화번호	string	전화번호
시행일자	int	시행일자
제개정구분	string	제개정구분
조문시행일자문자열	string	조문시행일자문자열
별표시행일자문자열	string	별표시행일자문자열
별표편집여부	string	별표편집여부
공포법령여부	string	공포법령여부
소관부처명	string	소관부처명
소관부처코드	int	소관부처코드
부서명	string	연락부서명
부서연락처	string	연락부서 전화번호
공동부령구분	string	공동부령의 구분
구분코드	string	구분코드(공동부령구분 구분코드)
공포번호	string	공포번호(공동부령의 공포번호)
조문번호	int	조문번호
조문가지번호	int	조문가지번호
조문여부	string	조문여부
조문제목	string	조문제목
조문시행일자	int	조문시행일자
조문제개정유형	string	조문제개정유형
조문이동이전	int	조문이동이전
조문이동이후	int	조문이동이후
조문변경여부	string	조문변경여부
(Y값이 있으면 해당 조문내에 변경 내용 있음 )
조문내용	string	조문내용
항번호	int	항번호
항제개정유형	string	항제개정유형
항제개정일자문자열	string	항제개정일자문자열
항내용	string	항내용
호번호	int	호번호
호내용	string	호내용
목번호	int	목번호
목내용	string	목내용
조문참고자료	string	조문참고자료
부칙공포일자	int	부칙공포일자
부칙공포번호	int	부칙공포번호
부칙내용	string	부칙내용
별표번호	int	별표번호
별표가지번호	int	별표가지번호
별표구분	string	별표구분
별표제목	string	별표제목
별표제목
문자열	string	별표제목문자열
별표시행일자	int	별표시행일자
별표서식
파일링크	string	별표서식파일링크
별표HWP
파일명	string	별표 HWP 파일명
별표서식
PDF파일링크	string	별표서식PDF파일링크
별표PDF
파일명	string	별표 PDF 파일명
별표이미지
파일명	string	별표 이미지 파일명
별표내용	string	별표내용
개정문내용	string	개정문내용
제개정이유내용	string	제개정이유내용

#3

법령 체계도 목록 조회 가이드API
※ 체계도 등 부가서비스는 법령서비스 신청을 하면 추가신청 없이 이용가능합니다.
- 요청 URL : http://www.law.go.kr/DRF/lawSearch.do?target=lsStmd
요청 변수 (request parameter)
요청변수	값	설명
OC	string(필수)	신청한 API인증값
target	string : lsStmd(필수)	서비스 대상
type	char(필수)	출력 형태 HTML/XML/JSON
query	string	법령명에서 검색을 원하는 질의
display	int	검색된 결과 개수 (default=20 max=100)
page	int	검색 결과 페이지 (default=1)
sort	string	정렬옵션(기본 : lasc 법령오름차순)
ldes : 법령내림차순
dasc : 공포일자 오름차순
ddes : 공포일자 내림차순
nasc : 공포번호 오름차순
ndes : 공포번호 내림차순
efasc : 시행일자 오름차순
efdes : 시행일자 내림차순
efYd	string	시행일자 범위 검색(20090101~20090130)
ancYd	string	공포일자 범위 검색(20090101~20090130)
date	int	공포일자 검색
nb	int	공포번호 검색
ancNo	string	공포번호 범위 검색 (10000~20000)
rrClsCd	string	법령 제개정 종류
(300201-제정 / 300202-일부개정 / 300203-전부개정
300204-폐지 / 300205-폐지제정 / 300206-일괄개정
300207-일괄폐지 / 300209-타법개정 / 300210-타법폐지
300208-기타)
org	string	소관부처별 검색(소관부처코드 제공)
knd	string	법령종류(코드제공)
gana	string	사전식 검색 (ga,na,da…,etc)
popYn	string	상세화면 팝업창 여부(팝업창으로 띄우고 싶을 때만 'popYn=Y')
샘플 URL
1. 자동차관리법 법령체계도 HTML 조회
http://www.law.go.kr/DRF/lawSearch.do?OC=test&target=lsStmd&type=HTML&query=자동차관리법
2. 'ㄱ'으로 시작하는 법령체계도 HTML조회
http://www.law.go.kr/DRF/lawSearch.do?OC=test&target=lsStmd&type=HTML&gana=ga
3. 법령체계도 XML 조회
http://www.law.go.kr/DRF/lawSearch.do?OC=test&target=lsStmd&type=XML
4. 법령체계도 JSON 조회
http://www.law.go.kr/DRF/lawSearch.do?OC=test&target=lsStmd&type=JSON
출력 결과 필드(response field)
필드	값	설명
target	string	검색서비스 대상
키워드	string	검색 단어
section	string	검색범위
totalCnt	int	검색 건수
page	int	현재 페이지번호
numOfRows	int	페이지 당 출력 결과 수
resultCode	int	조회 여부(성공 : 00 / 실패 : 01)
resultMsg	int	조회 여부(성공 : success / 실패 : fail)
law id	int	검색 결과 순번
법령 일련번호	int	법령 일련번호
법령명	string	법령명
법령ID	int	법령ID
공포일자	int	공포일자
공포번호	int	공포번호
제개정구분명	string	제개정구분명
소관부처코드	int	소관부처코드
소관부처명	string	소관부처명
법령구분명	string	법령구분명
시행일자	int	시행일자
본문 상세링크	string	본문 상세링크


#4

법령 체계도 본문 조회 가이드API
※ 체계도 등 부가서비스는 법령서비스 신청을 하면 추가신청 없이 이용가능합니다.
- 요청 URL : http://www.law.go.kr/DRF/lawService.do?target=lsStmd
요청 변수 (request parameter)
요청변수	값	설명
OC	string(필수)	신청한 API인증값
target	string : lsStmd(필수)	서비스 대상
type	char(필수)	출력 형태 : HTML/XML/JSON
ID	char	법령 ID (ID 또는 MST 중 하나는 반드시 입력)
MST	char	법령 마스터 번호 - 법령테이블의 lsi_seq 값을 의미함
LM	string	법령의 법령명(법령명 입력시 해당 법령 링크)
LD	int	법령의 공포일자
LN	int	법령의 공포번호
샘플 URL
1. 법령체계도 HTML 상세조회
http://www.law.go.kr/DRF/lawService.do?OC=test&target=lsStmd&MST=142362&type=HTML
http://www.law.go.kr/DRF/lawService.do?OC=test&target=lsStmd&MST=142591&type=HTML
2. 법령체계도 XML 상세조회
http://www.law.go.kr/DRF/lawService.do?OC=test&target=lsStmd&MST=142362&type=XML
3. 법령체계도 JSON 상세조회
http://www.law.go.kr/DRF/lawService.do?OC=test&target=lsStmd&MST=142362&type=JSON
출력 결과 필드(response field)
필드	값	설명
기본정보	string	기본정보
법령ID	int	법령ID
법령일련번호	int	법령일련번호
공포일자	int	공포일자
공포번호	int	공포번호
법종구분	string	법종구분
법령명	string	법령
시행일자	int	시행일자
제개정구분	string	제개정구분
상하위법	string	상하위법
법률	string	법률
시행령	string	시행령
시행규칙	string	시행규칙
본문 상세링크	string	본문 상세링크

#5

행정규칙 목록 조회 API
- 요청 URL : http://www.law.go.kr/DRF/lawSearch.do?target=admrul
요청 변수 (request parameter)
요청변수	값	설명
OC	string(필수)	신청한 API인증값
target	string : admrul(필수)	서비스 대상
type	char(필수)	출력 형태 : HTML/XML/JSON
nw	int	(1: 현행, 2: 연혁, 기본값: 현행)
search	int	검색범위 (기본 : 1 행정규칙명)
2 : 본문검색
query	string	검색범위에서 검색을 원하는 질의
(정확한 검색을 위한 문자열 검색 query="자동차")
display	int	검색된 결과 개수
(default=20 max=100)
page	int	검색 결과 페이지 (default=1)
org	string	소관부처별 검색(코드별도제공)
knd	string	행정규칙 종류별 검색
(1=훈령/2=예규/3=고시
/4=공고/5=지침/6=기타)
gana	string	사전식 검색 (ga,na,da…,etc)
sort	string	정렬옵션
(기본 : lasc 행정규칙명 오른차순)
ldes 행정규칙명 내림차순
dasc : 발령일자 오름차순
ddes : 발령일자 내림차순
nasc : 발령번호 오름차순
ndes : 발령번호 내림차순
efasc : 시행일자 오름차순
efdes : 시행일자 내림차순
date	int	행정규칙 발령일자
prmlYd	string	발령일자 기간검색(20090101~20090130)
modYd	string	수정일자 기간검색(20090101~20090130)
nb	int	행정규칙 발령번호
ex)제2023-8호 검색을 원할시 nb=20238
popYn	string	상세화면 팝업창 여부(팝업창으로 띄우고 싶을 때만 'popYn=Y')
샘플 URL
1. 행정규칙 HTML 목록 조회
http://www.law.go.kr/DRF/lawSearch.do?OC=test&target=admrul&query=학교&type=HTML
2. 행정규칙 XML 목록 조회
http://www.law.go.kr/DRF/lawSearch.do?OC=test&target=admrul&date=20250501&type=XML
3. 행정규칙 JSON 목록 조회
http://www.law.go.kr/DRF/lawSearch.do?OC=test&target=admrul&date=20250501&type=JSON
출력 결과 필드(response field)
필드	값	설명
target	string	검색서비스 대상
키워드	string	검색어
section	string	검색범위
totalCnt	int	검색건수
page	int	결과페이지번호
admrul id	int	결과 번호
행정규칙
일련번호	int	행정규칙일련번호
행정규칙명	string	행정규칙명
행정규칙종류	string	행정규칙종류
발령일자	int	발령일자
발령번호	int	발령번호
소관부처명	string	소관부처명
현행연혁구분	string	현행연혁구분
제개정
구분코드	string	제개정구분코드
제개정구분명	string	제개정구분명
행정규칙ID	int	행정규칙
행정규칙
상세링크	string	행정규칙상세링크
시행일자	int	시행일자
생성일자	int	생성일자

#6

행정규칙 본문 조회 API
- 요청 URL : http://www.law.go.kr/DRF/lawService.do?target=admrul
요청 변수 (request parameter)
요청변수	값	설명
OC	string(필수)	신청한 API인증값
target	string : admrul(필수)	서비스 대상
type	char(필수)	출력 형태 : HTML/XML/JSON
ID	char	행정규칙 일련번호
LID	char	행정규칙 ID
LM	string	행정규칙명 조회하고자 하는 정확한 행정규칙명을 입력
샘플 URL
1. 행정규칙 HTML 상세조회
http://www.law.go.kr/DRF/lawService.do?OC=test&target=admrul&ID=62505&type=HTML
2. 행정규칙 XML 상세조회
http://www.law.go.kr/DRF/lawService.do?OC=test&target=admrul&ID=10000005747&type=XML
3. 행정규칙 JSON 상세조회
http://www.law.go.kr/DRF/lawService.do?OC=test&target=admrul&ID=2000000091702&type=JSON
출력 결과 필드(response field)
필드	값	설명
행정규칙
일련번호	int	행정규칙일련번호
행정규칙명	string	행정규칙명
행정규칙종류	string	행정규칙종류
행정규칙종류코드	string	행정규칙종류코드
발령일자	int	발령일자
발령번호	string	발령번호
제개정구분명	string	제개정구분명
제개정
구분코드	string	제개정구분코드
조문형식여부	string	조문형식여부
행정규칙ID	int	행정규칙
소관부처명	string	소관부처명
소관부처코드	string	소관부처코드
상위부처명	string	상위부처명
담당부서기관코드	string	담당부서기관코드
담당부서기관명	string	담당부서기관명
담당자명	string	담당자명
전화번호	string	전화번호
현행여부	string	현행여부
시행일자	string	시행일자
생성일자	string	생성일자
조문내용	string	조문내용
부칙	string	부칙
부칙공포일자	int	부칙공포일자
부칙공포번호	int	부칙공포번호
부칙내용	string	부칙내용
별표	string	별표
별표번호	int	별표번호
별표가지번호	int	별표가지번호
별표구분	string	별표구분
별표제목	string	별표제목
별표서식파일링크	string	별표서식파일링크
별표서식PDF파일링크	string	별표서식PDF파일링크
별표내용	string	별표내용
첨부파일	string	첨부파일
첨부파일명	string	첨부파일명
첨부파일링크	string	첨부파일링크