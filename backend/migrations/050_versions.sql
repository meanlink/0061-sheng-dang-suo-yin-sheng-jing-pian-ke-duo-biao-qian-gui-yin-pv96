-- 同一卷多版本补正：版本簿与按版本留存的片刻/候选/签发/索引。
-- 旧的四张 sound_* 表始终是“当前签发版”的投影，签齐切换前保持完整旧版。
ALTER TABLE sound_archives ADD COLUMN IF NOT EXISTS current_version int NOT NULL DEFAULT 1;

CREATE TABLE IF NOT EXISTS sound_archive_versions(
 archive text NOT NULL REFERENCES sound_archives(code),
 version int NOT NULL CHECK(version>=1),
 status text NOT NULL DEFAULT 'open' CHECK(status IN('open','published')),
 request_key text,
 digest text, note text, created_by text,
 created_at timestamptz NOT NULL DEFAULT now(),
 published_at timestamptz,
 PRIMARY KEY(archive,version),
 UNIQUE(archive,request_key)
);
-- 同一卷至多一个尚未签发齐全的补正草稿版本（version>current_version）。
CREATE UNIQUE INDEX IF NOT EXISTS sound_versions_one_draft
 ON sound_archive_versions(archive) WHERE status='open' AND version>1;

CREATE TABLE IF NOT EXISTS sound_clip_versions(
 archive text NOT NULL, version int NOT NULL, number int NOT NULL CHECK(number>0),
 start_s int NOT NULL CHECK(start_s>=0), end_s int NOT NULL,
 voices real NOT NULL CHECK(voices BETWEEN 0 AND 1),
 movement real NOT NULL CHECK(movement BETWEEN 0 AND 1),
 engines real NOT NULL CHECK(engines BETWEEN 0 AND 1),
 surf real NOT NULL CHECK(surf BETWEEN 0 AND 1),
 content_hash text NOT NULL, rev int NOT NULL DEFAULT 1, revised boolean NOT NULL DEFAULT false,
 PRIMARY KEY(archive,version,number),
 FOREIGN KEY(archive,version) REFERENCES sound_archive_versions(archive,version) ON DELETE CASCADE,
 CHECK(end_s>start_s)
);

CREATE TABLE IF NOT EXISTS sound_score_versions(
 archive text NOT NULL, version int NOT NULL, number int NOT NULL,
 label text NOT NULL CHECK(label IN('crowd','motor','water')),
 score numeric(8,6) NOT NULL CHECK(score BETWEEN 0 AND 1),
 factors jsonb NOT NULL, content_hash text NOT NULL,
 PRIMARY KEY(archive,version,number,label),
 FOREIGN KEY(archive,version,number)
   REFERENCES sound_clip_versions(archive,version,number) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sound_review_versions(
 archive text NOT NULL, version int NOT NULL, number int NOT NULL,
 note text NOT NULL CHECK(length(note)>=6), signer text NOT NULL,
 inherited boolean NOT NULL DEFAULT false,
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(archive,version,number),
 FOREIGN KEY(archive,version,number)
   REFERENCES sound_clip_versions(archive,version,number) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sound_index_versions(
 archive text NOT NULL, version int NOT NULL, number int NOT NULL, label text NOT NULL,
 PRIMARY KEY(archive,version,number,label),
 FOREIGN KEY(archive,version,number)
   REFERENCES sound_review_versions(archive,version,number) ON DELETE CASCADE,
 FOREIGN KEY(archive,version,number,label)
   REFERENCES sound_score_versions(archive,version,number,label)
);
