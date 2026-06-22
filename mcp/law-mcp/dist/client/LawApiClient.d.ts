import type { LawSearchResult, LawFullText, LawArticle, LawHierarchy, AdminRuleText, AdminRuleSearchResult } from '../types/index.js';
export declare function searchLaw(query: string): Promise<LawSearchResult[]>;
export declare function getLawText(lawId: string): Promise<LawFullText>;
export declare function getLawHierarchy(lawId: string): Promise<LawHierarchy>;
export declare function searchAdminRule(query: string): Promise<AdminRuleSearchResult[]>;
export declare function getAdminRuleText(ruleSerialNo: string): Promise<AdminRuleText>;
export declare function getLawArticle(lawId: string, articleNumber: number, subNumber?: number): Promise<LawArticle | null>;
