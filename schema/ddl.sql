-- LawQuery 법령 DB 표준 스키마 (ldb_j 에서 추출·표준화)
-- 적재 대상 DB(ldb_<코드>)는 loader 가 별도로 CREATE DATABASE 한 뒤 이 파일을 USE 상태에서 실행한다.
-- collation: utf8mb4_uca1400_ai_ci (본체와 동일)

-- 법(Act)
CREATE TABLE IF NOT EXISTS `db_a` (
  `_pk` bigint(20) NOT NULL AUTO_INCREMENT,
  `seq` bigint(20) DEFAULT NULL,
  `id_aa` text DEFAULT NULL,                -- 조 묶음 ID (표시용, 예: A2)
  `id_a` text DEFAULT NULL,                 -- 노드 ID (세부, 예: A2_3h). 장/절 제목행은 NULL
  `title_a` text DEFAULT NULL,
  `content_a` text DEFAULT NULL,
  `content_a_sched` text DEFAULT NULL COMMENT '시행예정 내용',
  `sched_date` varchar(10) DEFAULT NULL,
  PRIMARY KEY (`_pk`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;

-- 시행령(Enforcement Decree)
CREATE TABLE IF NOT EXISTS `db_e` (
  `_pk` bigint(20) NOT NULL AUTO_INCREMENT,
  `seq` bigint(20) DEFAULT NULL,
  `id_e` text DEFAULT NULL,
  `content_e` text DEFAULT NULL,
  `content_e_sched` text DEFAULT NULL COMMENT '시행예정 내용',
  `sched_date` varchar(10) DEFAULT NULL,
  PRIMARY KEY (`_pk`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;

-- 감독규정(Supervisory Regulation)
CREATE TABLE IF NOT EXISTS `db_s` (
  `_pk` bigint(20) NOT NULL AUTO_INCREMENT,
  `seq` bigint(20) DEFAULT NULL,
  `id_s` text DEFAULT NULL,
  `content_s` text DEFAULT NULL,
  `content_s_sched` text DEFAULT NULL COMMENT '시행예정 내용',
  `sched_date` varchar(10) DEFAULT NULL,
  PRIMARY KEY (`_pk`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;

-- 감독규정시행세칙(Supervisory Rules)
CREATE TABLE IF NOT EXISTS `db_r` (
  `_pk` bigint(20) NOT NULL AUTO_INCREMENT,
  `seq` bigint(20) DEFAULT NULL,
  `id_r` text DEFAULT NULL,
  `content_r` text DEFAULT NULL,
  `content_r_sched` text DEFAULT NULL COMMENT '시행예정 내용',
  `sched_date` varchar(10) DEFAULT NULL,
  PRIMARY KEY (`_pk`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;

-- 5단째 본문 단(시행규칙 등 추가 단). 4단 법은 빈 테이블. 백엔드는 db_meta 단수로 step 판단.
CREATE TABLE IF NOT EXISTS `db_b` (
  `_pk` bigint(20) NOT NULL AUTO_INCREMENT,
  `seq` bigint(20) DEFAULT NULL,
  `id_b` text DEFAULT NULL,
  `content_b` text DEFAULT NULL,
  `content_b_sched` text DEFAULT NULL COMMENT '시행예정 내용',
  `sched_date` varchar(10) DEFAULT NULL,
  PRIMARY KEY (`_pk`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;

-- 별표
CREATE TABLE IF NOT EXISTS `db_annex` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `origin` enum('a','e','s','r','b') NOT NULL COMMENT '원규정 타입',
  `id_annex` varchar(100) NOT NULL COMMENT '별표 자체 ID (예: A_A1)',
  `annex_no` varchar(255) DEFAULT NULL,
  `id_src` varchar(100) NOT NULL COMMENT '별표를 호출하는 규정 ID (예: A3, E12)',
  `annex_name` varchar(255) DEFAULT NULL COMMENT '별표명',
  `annex_url` text DEFAULT NULL COMMENT '별표링크',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci COMMENT='별표 개별 데이터';

-- 법령명 메타 (단별 1행: origin a/e/s/r)
CREATE TABLE IF NOT EXISTS `db_meta` (
  `_pk` int(11) NOT NULL AUTO_INCREMENT,
  `origin` char(1) NOT NULL,
  `full_name` text DEFAULT NULL,
  `short_name` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`_pk`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;

-- 참조
CREATE TABLE IF NOT EXISTS `db_ref` (
  `_pk` bigint(20) NOT NULL AUTO_INCREMENT,
  `id` bigint(20) DEFAULT NULL,
  `id_origin` text DEFAULT NULL,
  `ref_type` text DEFAULT NULL,
  `ref_target` text DEFAULT NULL,
  `ref_content` text DEFAULT NULL,
  PRIMARY KEY (`_pk`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;

-- 연계 엣지 (id_start → id_end). 5단 연계의 핵심.
CREATE TABLE IF NOT EXISTS `rdb` (
  `_pk` bigint(20) NOT NULL AUTO_INCREMENT,
  `id` bigint(20) DEFAULT NULL,
  `id_start` text DEFAULT NULL,
  `id_end` text DEFAULT NULL,
  PRIMARY KEY (`_pk`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;

-- 인용 정밀 강조쌍: 하위 조의 어느 항/호(down_id)가 상위 조의 어느 항/호(up_id)를 인용하는가.
-- rdb(조 단위 트리)는 그대로, 연계표/팝업에서 '실제 참조된 부분'만 강조하는 데 사용.
CREATE TABLE IF NOT EXISTS `db_rdb_hl` (
  `_pk` bigint(20) NOT NULL AUTO_INCREMENT,
  `id` bigint(20) DEFAULT NULL,
  `up_id` text DEFAULT NULL,
  `down_id` text DEFAULT NULL,
  PRIMARY KEY (`_pk`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;

-- 벌칙 (선택)
CREATE TABLE IF NOT EXISTS `db_penalty` (
  `_pk` bigint(20) NOT NULL AUTO_INCREMENT,
  `id` bigint(20) DEFAULT NULL,
  `penalty_a_phy` text DEFAULT NULL,
  `penalty_a_log` text DEFAULT NULL,
  PRIMARY KEY (`_pk`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;

CREATE TABLE IF NOT EXISTS `db_penalty_a` (
  `_pk` bigint(20) NOT NULL AUTO_INCREMENT,
  `id` bigint(20) DEFAULT NULL,
  `category` text DEFAULT NULL,
  `item_a_phy` text DEFAULT NULL,
  `item_a_log` text DEFAULT NULL,
  `content_pa` text DEFAULT NULL,
  `penalty_a_phy` text DEFAULT NULL,
  `id_a` text DEFAULT NULL,
  PRIMARY KEY (`_pk`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;

CREATE TABLE IF NOT EXISTS `db_penalty_e` (
  `_pk` bigint(20) NOT NULL AUTO_INCREMENT,
  `id` bigint(20) DEFAULT NULL,
  `content_pe` text DEFAULT NULL,
  `item_a_log` text DEFAULT NULL,
  `penalty_e_log` text DEFAULT NULL,
  `item_a_phy` text DEFAULT NULL,
  PRIMARY KEY (`_pk`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
