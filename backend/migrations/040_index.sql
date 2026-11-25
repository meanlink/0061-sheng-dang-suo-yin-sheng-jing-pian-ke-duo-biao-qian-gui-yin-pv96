CREATE TABLE IF NOT EXISTS sound_reviews(
 archive text NOT NULL, number int NOT NULL, note text NOT NULL CHECK(length(note)>=6), signer text NOT NULL,
 PRIMARY KEY(archive,number), FOREIGN KEY(archive,number) REFERENCES sound_clips(archive,number)
);
CREATE TABLE IF NOT EXISTS sound_index(
 archive text NOT NULL, number int NOT NULL, label text NOT NULL,
 PRIMARY KEY(archive,number,label),
 FOREIGN KEY(archive,number) REFERENCES sound_reviews(archive,number),
 FOREIGN KEY(archive,number,label) REFERENCES sound_scores(archive,number,label)
);
