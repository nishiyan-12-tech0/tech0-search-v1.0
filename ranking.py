from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from datetime import datetime

class SearchEngine:
    """TF-IDFベースの検索エンジン（ranking.py の本体）"""

    def __init__(self):
        # TF-IDF ベクトライザーを初期化する
        self.vectorizer = TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 2),  # ユニグラム（1語）とバイグラム（隣り合う2語のまとまり）を両方使う
            min_df=1,
            max_df=0.95,
            sublinear_tf=True    # TF の対数スケーリング
        )
        self.tfidf_matrix = None  # インデックス（後で構築）
        self.pages = []           # 元のページデータを保持
        self.is_fitted = False    # インデックスが構築済みかのフラグ

    def build_index(self, pages: list):
        """
        全ページの TF-IDF インデックスを構築する。

        Args:
            pages: ページ情報の辞書リスト
        """
        if not pages:
            return

        self.pages = pages

        # 各ページの「検索対象テキスト」を組み立てる
        # タイトル・説明・キーワードに重みを付けるため、文字列を繰り返す
        corpus = []
        for p in pages:
            # keywords がカンマ区切り文字列の場合はリストに変換する
            kw = p.get("keywords", "") or ""
            if isinstance(kw, str):
                kw_list = [k.strip() for k in kw.split(",") if k.strip()]
            else:
                kw_list = kw

            # 重みづけを実施。タイトルは 3倍、説明は 2倍、キーワードは 2倍の重みを付ける
            text = " ".join([
                (p.get("title", "") + " ") * 3,        # タイトルは3倍
                (p.get("description", "") + " ") * 2,  # 説明は2倍
                (p.get("full_text", "") + " "),        # 本文
                (" ".join(kw_list) + " ") * 2,         # キーワードは2倍
            ])
            corpus.append(text)

        # TF-IDF マトリックスを構築する
        self.tfidf_matrix = self.vectorizer.fit_transform(corpus)
        self.is_fitted = True
        print(f"インデックス構築完了：{len(pages)} ページ")

    def search(self, query: str, top_n: int = 20) -> list:
        """
        TF-IDF ベースの検索を実行する。

        Args:
            query : 検索クエリ
            top_n : 返す結果の最大数

        Returns:
            スコア付きの検索結果リスト
        """
        if not self.is_fitted or not query.strip():
            return []

        # クエリをベクトル化してコサイン類似度を計算する（Step 3 で学んだ内容）
        query_vec = self.vectorizer.transform([query])
        similarities = cosine_similarity(query_vec, self.tfidf_matrix)[0]

        # 閾値以上のページだけ結果に含める
        results = []
        for idx, base_score in enumerate(similarities):
            if base_score > 0.01:
                page = self.pages[idx].copy()

                # 追加スコアリングで最終スコアを計算する
                final_score = self._calculate_final_score(page, base_score, query)

                # スコアをパーセント表示用に変換する
                page["relevance_score"] = round(float(final_score) * 100, 1)
                page["base_score"] = round(float(base_score) * 100, 1)
                results.append(page)

        # スコアの高い順に並べて top_n 件を返す
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return results[:top_n]

    def _calculate_final_score(self, page: dict, base_score: float, query: str) -> float:
        """
        複数の要素を組み合わせて最終スコアを計算する（内部メソッド）。
        Args:
            page: ページ情報
            base_score: TF-IDFベーススコア
            query: 検索クエリ

        Returns:
            最終スコア
        """
        score = base_score
        query_lower = query.lower()

        # 1. タイトルマッチボーナス
        title = page.get("title", "").lower()
        if query_lower == title:
            score *= 1.8          # 完全一致：+80%
        elif query_lower in title:
            score *= 1.4          # 部分一致：+40%

        # 2. キーワードマッチボーナス
        keywords = page.get("keywords", [])

        if isinstance(keywords, str):
            keywords = keywords.split(",")

        keywords_lower = [k.strip().lower() for k in keywords]

        if query_lower in keywords_lower:
            score *= 1.3  # キーワード一致：+30%

        # 3. 新鮮度ボーナス（90日以内のページは最大 +20%）
        crawled_at = page.get("crawled_at", "")
        if crawled_at:
            try:
                crawled = datetime.fromisoformat(crawled_at.replace("Z", "+00:00"))
                days_old = (datetime.now() - crawled.replace(tzinfo=None)).days
                if days_old <= 90:
                    recency_bonus = 1 + (0.2 * (90 - days_old) / 90)
                    score *= recency_bonus
            except Exception:
                pass

        # 4. 文字数による調整
        word_count = page.get("word_count", 0)
        if word_count < 50:
            score *= 0.7          # 短すぎるページは減点
        elif word_count > 10000:
            score *= 0.85         # 長すぎるページは少し減点

        return score


# シングルトンの追加（4-6で学んだ内容）
_engine = None
def get_engine() -> SearchEngine:
    global _engine
    if _engine is None:
        _engine = SearchEngine()
    return _engine


def rebuild_index(pages: list):
    """インデックスを再構築する（新しいページが追加されたときに呼び出す）"""
    engine = get_engine()
    engine.build_index(pages)