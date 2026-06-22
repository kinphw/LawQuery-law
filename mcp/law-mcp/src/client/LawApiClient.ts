import axios from 'axios';
import type {
  LawSearchResult, LawFullText, LawArticle,
  Hang, Ho, Mok,
  RawLawSearchItem, RawArticle, RawHang, RawHo, RawMok,
  LawHierarchy, LawTierInfo, AdminRuleEntry, AdminRuleText,
  AdminRuleSearchResult,
} from '../types/index.js';

const BASE_URL = 'http://www.law.go.kr/DRF';

function getOC(): string {
  const oc = process.env.LAW_OC;
  if (!oc) throw new Error('LAW_OC 환경변수가 설정되지 않았습니다.');
  return oc;
}

// ECONNRESET 등 일시적 네트워크 오류 재시도
const RETRYABLE_CODES = new Set(['ECONNRESET', 'ETIMEDOUT', 'ECONNABORTED', 'ENOTFOUND', 'EAI_AGAIN']);

async function axiosGetWithRetry<T>(
  url: string,
  params: Record<string, string | number>,
  maxRetries = 3,
): Promise<T> {
  let lastError: unknown;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const res = await axios.get<T>(url, { params, timeout: 15_000 });
      return res.data;
    } catch (e: unknown) {
      lastError = e;
      const code = (e as { code?: string })?.code ?? '';
      const status = (e as { response?: { status?: number } })?.response?.status;
      const retryable = RETRYABLE_CODES.has(code) || status === 503 || status === 429;
      if (!retryable || attempt === maxRetries) break;
      const wait = 1000 * (attempt + 1);
      await new Promise(r => setTimeout(r, wait));
    }
  }
  throw lastError;
}

// --- 정규화 헬퍼 (object | array 불일치 처리) ---

function toArray<T>(val: T | T[] | undefined): T[] {
  if (val === undefined || val === null) return [];
  return Array.isArray(val) ? val : [val];
}

function normalizeMok(raw: RawMok | RawMok[] | undefined): Mok[] {
  return toArray(raw).map(m => ({ 목번호: m.목번호 ?? '', 목내용: m.목내용 ?? '' }));
}

function normalizeHo(raw: RawHo | RawHo[] | undefined): Ho[] {
  return toArray(raw).map(h => ({
    호번호: h.호번호 ?? '',
    호내용: h.호내용 ?? '',
    목목록: normalizeMok(h.목),
  }));
}

function normalizeHang(raw: RawHang | RawHang[] | undefined): Hang[] {
  return toArray(raw).map(h => ({
    항번호: h.항번호 ?? '',
    항내용: h.항내용 ?? '',
    호목록: normalizeHo(h.호),
  }));
}

function parseArticle(raw: RawArticle): LawArticle {
  const subNo = raw.조문가지번호 ? `의${raw.조문가지번호}` : '';
  const content = Array.isArray(raw.조문내용)
    ? (raw.조문내용 as string[][]).flat().join('\n')
    : (raw.조문내용 ?? '');

  return {
    조번호: `${raw.조문번호}${subNo}`,
    조제목: raw.조문제목 ?? '',
    조문내용: content,
    항목록: normalizeHang(raw.항),
  };
}

// --- 공개 API ---

export async function searchLaw(query: string): Promise<LawSearchResult[]> {
  const data = await axiosGetWithRetry<Record<string, unknown>>(
    `${BASE_URL}/lawSearch.do`,
    { OC: getOC(), target: 'eflaw', type: 'JSON', query, nw: 3 },
  );

  const items: RawLawSearchItem[] = toArray((data as any)?.LawSearch?.law);
  return items
    .filter(l => l.현행연혁코드 === '현행')
    .map(l => ({
      법령ID: l.법령ID,
      법령명한글: l.법령명한글,
      법령구분명: l.법령구분명,
      시행일자: l.시행일자,
      소관부처명: l.소관부처명,
    }));
}

export async function getLawText(lawId: string): Promise<LawFullText> {
  const raw = await axiosGetWithRetry<Record<string, unknown>>(
    `${BASE_URL}/lawService.do`,
    { OC: getOC(), target: 'eflaw', type: 'JSON', ID: lawId },
  );

  const data = (raw as any)?.법령;
  if (!data) throw new Error(`법령ID ${lawId}에 해당하는 법령을 찾을 수 없습니다.`);

  const info = data.기본정보;
  const articles: LawArticle[] = toArray<RawArticle>(data.조문?.조문단위)
    .filter(j => j.조문여부 === '조문')
    .map(parseArticle);

  return {
    법령명: info?.법령명_한글 ?? '',
    법령ID: info?.법령ID ?? lawId,
    시행일자: info?.시행일자 ?? '',
    소관부처명: info?.소관부처?.content ?? '',
    조문목록: articles,
  };
}

// 체계도 내 행정규칙 객체에서 목록 추출 (종류별로 object|array 혼재)
function extractAdminRules(admrul: Record<string, unknown> | undefined): AdminRuleEntry[] {
  if (!admrul || typeof admrul !== 'object') return [];
  const results: AdminRuleEntry[] = [];
  for (const [종류, items] of Object.entries(admrul)) {
    const arr = Array.isArray(items) ? items : [items];
    for (const item of arr as any[]) {
      const info = item?.기본정보;
      if (info?.행정규칙일련번호) {
        results.push({
          종류,
          행정규칙명: info.행정규칙명 ?? '',
          행정규칙일련번호: info.행정규칙일련번호,
          시행일자: info.시행일자 ?? '',
        });
      }
    }
  }
  return results;
}

function extractTierInfo(tier: any): LawTierInfo | null {
  const info = tier?.기본정보;
  if (!info?.법령ID) return null;
  return {
    법령ID: info.법령ID,
    법령명: info.법령명 ?? '',
    법종구분: info.법종구분?.content ?? '',
    시행일자: info.시행일자 ?? '',
    행정규칙목록: extractAdminRules(tier.행정규칙),
  };
}

export async function getLawHierarchy(lawId: string): Promise<LawHierarchy> {
  const raw = await axiosGetWithRetry<Record<string, unknown>>(
    `${BASE_URL}/lawService.do`,
    { OC: getOC(), target: 'lsStmd', ID: lawId, type: 'JSON' },
  );

  const data = (raw as any)?.법령체계도;
  if (!data) throw new Error(`법령ID ${lawId}의 체계도를 찾을 수 없습니다.`);

  const 기본 = data.기본정보;
  const 상하위 = data.상하위법;
  const 법률tier = 상하위?.법률;

  const hierarchy: LawHierarchy = {
    법령명: 기본?.법령명 ?? '',
    법령ID: 기본?.법령ID ?? lawId,
    법률: extractTierInfo(법률tier) ?? undefined,
    시행령: extractTierInfo(법률tier?.시행령) ?? undefined,
    시행규칙: extractTierInfo(법률tier?.시행령?.시행규칙) ?? undefined,
  };

  return hierarchy;
}

// 행정규칙명으로 검색 (target=admrul, section=admRulNm default).
// 현행 행정규칙만 필터 (현행연혁=현행).
export async function searchAdminRule(query: string): Promise<AdminRuleSearchResult[]> {
  const data = await axiosGetWithRetry<Record<string, unknown>>(
    `${BASE_URL}/lawSearch.do`,
    { OC: getOC(), target: 'admrul', type: 'JSON', query },
  );

  const items = toArray((data as any)?.AdmRulSearch?.admrul) as any[];
  return items
    .filter(r => (r?.현행연혁구분 ?? '현행') === '현행')
    .map(r => ({
      행정규칙일련번호: String(r.행정규칙일련번호 ?? ''),
      행정규칙명: String(r.행정규칙명 ?? ''),
      행정규칙종류: String(r.행정규칙종류 ?? ''),
      소관부처명: String(r.소관부처명 ?? ''),
      시행일자: String(r.시행일자 ?? ''),
      발령일자: String(r.발령일자 ?? ''),
      현행여부: String(r.현행연혁구분 ?? ''),
    }))
    .filter(r => r.행정규칙일련번호);
}

export async function getAdminRuleText(ruleSerialNo: string): Promise<AdminRuleText> {
  const raw = await axiosGetWithRetry<Record<string, unknown>>(
    `${BASE_URL}/lawService.do`,
    { OC: getOC(), target: 'admrul', ID: ruleSerialNo, type: 'JSON' },
  );

  const svc = (raw as any)?.AdmRulService;
  if (!svc) throw new Error(`행정규칙 일련번호 ${ruleSerialNo}를 찾을 수 없습니다.`);

  const info = svc.행정규칙기본정보 ?? {};
  const 조문raw = svc.조문내용;
  const 조문내용 = Array.isArray(조문raw)
    ? 조문raw.join('\n')
    : typeof 조문raw === 'string'
      ? 조문raw
      : '';

  return {
    행정규칙명: info.행정규칙명 ?? '',
    행정규칙일련번호: info.행정규칙일련번호 ?? ruleSerialNo,
    행정규칙종류: info.행정규칙종류 ?? '',
    발령일자: info.발령일자 ?? '',
    소관부처명: info.소관부처명 ?? '',
    시행일자: info.시행일자 ?? '',
    조문내용,
  };
}

export async function getLawArticle(
  lawId: string,
  articleNumber: number,
  subNumber: number = 0,
): Promise<LawArticle | null> {
  // JO 형식: 조번호 4자리 + 가지번호 2자리
  const jo = String(articleNumber).padStart(4, '0') + String(subNumber).padStart(2, '0');

  const raw = await axiosGetWithRetry<Record<string, unknown>>(
    `${BASE_URL}/lawService.do`,
    { OC: getOC(), target: 'eflaw', type: 'JSON', ID: lawId, JO: jo },
  );

  const articles: RawArticle[] = toArray<RawArticle>((raw as any)?.법령?.조문?.조문단위)
    .filter(j => j.조문여부 === '조문');

  if (articles.length === 0) return null;
  return parseArticle(articles[0]);
}
