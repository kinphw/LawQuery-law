export interface LawSearchResult {
  법령ID: string;
  법령명한글: string;
  법령구분명: string;
  시행일자: string;
  소관부처명: string;
}

export interface Mok {
  목번호: string;
  목내용: string;
}

export interface Ho {
  호번호: string;
  호내용: string;
  목목록: Mok[];
}

export interface Hang {
  항번호: string;
  항내용: string;
  호목록: Ho[];
}

export interface LawArticle {
  조번호: string;
  조제목: string;
  조문내용: string;
  항목록: Hang[];
}

export interface LawFullText {
  법령명: string;
  법령ID: string;
  시행일자: string;
  소관부처명: string;
  조문목록: LawArticle[];
}

// 국가법령정보 API raw 응답 타입
export interface RawLawSearchItem {
  현행연혁코드: string;
  법령ID: string;
  법령명한글: string;
  법령구분명: string;
  시행일자: string;
  소관부처명: string;
  법령일련번호: string;
}

export interface RawMok {
  목번호: string;
  목내용: string;
}

export interface RawHo {
  호번호: string;
  호내용: string;
  목?: RawMok | RawMok[];
}

export interface RawHang {
  항번호: string;
  항내용: string;
  호?: RawHo | RawHo[];
}

export interface RawArticle {
  조문번호: string;
  조문가지번호?: string;
  조문여부: string;
  조문제목: string;
  조문내용: string | string[][];
  항?: RawHang | RawHang[];
}

// 법령체계도
export interface LawTierInfo {
  법령ID: string;
  법령명: string;
  법종구분: string;
  시행일자: string;
  행정규칙목록: AdminRuleEntry[];
}

export interface AdminRuleEntry {
  종류: string;
  행정규칙명: string;
  행정규칙일련번호: string;
  시행일자: string;
}

export interface LawHierarchy {
  법령명: string;
  법령ID: string;
  법률?: LawTierInfo;
  시행령?: LawTierInfo;
  시행규칙?: LawTierInfo;
}

// 행정규칙 검색 결과 (lawSearch.do?target=admrul)
export interface AdminRuleSearchResult {
  행정규칙일련번호: string;
  행정규칙명: string;
  행정규칙종류: string;
  소관부처명: string;
  시행일자: string;
  발령일자: string;
  현행여부: string;
}

// 행정규칙
export interface AdminRuleText {
  행정규칙명: string;
  행정규칙일련번호: string;
  행정규칙종류: string;
  발령일자: string;
  소관부처명: string;
  시행일자: string;
  조문내용: string;
}
