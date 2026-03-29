-- schema.sql
-- Tech0 Search v1.0 データベース設計

-- pagesテーブル（メイン）
-- UNIQUE 制約：同じ URL は重複して登録できない
CREATE TABLE IF NOT EXISTS pages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    url         TEXT NOT NULL UNIQUE,
    title       TEXT NOT NULL,
    description TEXT,
    full_text   TEXT,
    author      TEXT,
    category    TEXT,
    word_count  INTEGER DEFAULT 0,
    crawled_at  DATETIME,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- keywordsテーブル（TF-IDFスコア保存）
-- page_id が削除されたら自動的にキーワードも削除される（ON DELETE CASCADE）
CREATE TABLE IF NOT EXISTS keywords (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    page_id     INTEGER NOT NULL,
    keyword     TEXT NOT NULL,
    tf_score    REAL DEFAULT 0.0,
    tfidf_score REAL DEFAULT 0.0,
    FOREIGN KEY (page_id) REFERENCES pages(id) ON DELETE CASCADE
);

-- 検索ログテーブル（発展用）
CREATE TABLE IF NOT EXISTS search_logs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    query         TEXT NOT NULL,
    results_count INTEGER DEFAULT 0,
    user_id       TEXT,
    searched_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- クリックログテーブル（発展用）
CREATE TABLE IF NOT EXISTS click_logs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    search_log_id INTEGER,
    page_id       INTEGER NOT NULL,
    position      INTEGER,
    clicked_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (search_log_id) REFERENCES search_logs(id),
    FOREIGN KEY (page_id) REFERENCES pages(id)
);

-- インデックス作成（検索を高速化する）
CREATE INDEX IF NOT EXISTS idx_keyword    ON keywords(keyword);
CREATE INDEX IF NOT EXISTS idx_page_id    ON keywords(page_id);
CREATE INDEX IF NOT EXISTS idx_search_query ON search_logs(query);
CREATE INDEX IF NOT EXISTS idx_search_date  ON search_logs(searched_at);
