CREATE TABLE IF NOT EXISTS sound_archives(
 code text PRIMARY KEY, title text NOT NULL, record_date date NOT NULL,
 duration int NOT NULL CHECK(duration BETWEEN 20 AND 3600),
 state text NOT NULL DEFAULT 'listening' CHECK(state IN('listening','sealed','scored','indexed'))
);
