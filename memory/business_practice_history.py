"""Append-only practice samples and owner assessments, including legacy imports."""
import json


def init_history(cursor):
    cursor.execute('''CREATE TABLE IF NOT EXISTS business_practice_samples (
        id INTEGER PRIMARY KEY AUTOINCREMENT, brief_id INTEGER NOT NULL,
        attempt INTEGER NOT NULL, sample TEXT NOT NULL, created_at TEXT NOT NULL,
        parent_sample_id INTEGER, feedback_review_id INTEGER, changes TEXT NOT NULL DEFAULT '',
        UNIQUE(brief_id, attempt)
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS business_practice_reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT, sample_id INTEGER NOT NULL,
        review_json TEXT NOT NULL, supersedes_review_id INTEGER
    )''')
    cursor.execute('CREATE INDEX IF NOT EXISTS business_review_order ON business_practice_reviews(sample_id,id)')
    for table in ('business_practice_samples', 'business_practice_reviews'):
        for operation in ('UPDATE', 'DELETE'):
            cursor.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_no_{operation.lower()} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT, 'Practice history is append-only'); END")  # nosec B608 # Literal identifiers/operations only.
    # Imports are idempotent; original text/timestamps/assessments are preserved.
    rows = cursor.execute('''SELECT b.id,b.sample,b.sample_created_at,b.created_at,b.review_json FROM business_discovery b WHERE sample IS NOT NULL
        AND NOT EXISTS (SELECT 1 FROM business_practice_samples s WHERE s.brief_id=b.id)''').fetchall()
    for ident, sample, sample_created_at, created_at, review_json in rows:
        cursor.execute('''INSERT INTO business_practice_samples(brief_id,attempt,sample,created_at)
            VALUES (?,1,?,?)''', (ident, sample, sample_created_at or created_at))
        sample_id = cursor.lastrowid
        if review_json:
            cursor.execute('INSERT INTO business_practice_reviews(sample_id,review_json) VALUES (?,?)', (sample_id, review_json))


def history(cursor, ident):
    samples = [dict(row) for row in cursor.execute('SELECT * FROM business_practice_samples WHERE brief_id=? ORDER BY attempt', (ident,))]
    for sample in samples:
        sample['reviews'] = []
        for row in cursor.execute('SELECT * FROM business_practice_reviews WHERE sample_id=? ORDER BY id', (sample['id'],)):
            review = dict(row)
            review['review'] = json.loads(review.pop('review_json'))
            sample['reviews'].append(review)
    return samples
