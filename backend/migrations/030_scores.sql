CREATE TABLE IF NOT EXISTS sound_scores(
 archive text NOT NULL, number int NOT NULL,
 label text NOT NULL CHECK(label IN('crowd','motor','water')),
 score numeric(8,6) NOT NULL CHECK(score BETWEEN 0 AND 1),
 factors jsonb NOT NULL,
 PRIMARY KEY(archive,number,label),
 FOREIGN KEY(archive,number) REFERENCES sound_clips(archive,number)
);
