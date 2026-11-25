CREATE TABLE IF NOT EXISTS sound_clips(
 archive text NOT NULL REFERENCES sound_archives(code), number int NOT NULL CHECK(number>0),
 start_s int NOT NULL CHECK(start_s>=0), end_s int NOT NULL,
 voices real NOT NULL CHECK(voices BETWEEN 0 AND 1), movement real NOT NULL CHECK(movement BETWEEN 0 AND 1),
 engines real NOT NULL CHECK(engines BETWEEN 0 AND 1), surf real NOT NULL CHECK(surf BETWEEN 0 AND 1),
 PRIMARY KEY(archive,number), CHECK(end_s>start_s)
);
