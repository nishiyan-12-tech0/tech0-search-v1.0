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
 
            # 重みづけを実施。タイトルは3倍、説明は2倍、キーワードは2倍の重みを付ける
            text = " ".join([
                (p.get("title", "") + " ") * 3,        # タイトルは3倍
                (p.get("description", "") + " ") * 2,  # 説明は2倍
                (p.get("full_text", "") + " "),         # 本文
                (" ".join(kw_list) + " ") * 2,          # キーワードは2倍
            ])
            corpus.append(text)
 
        # TF-IDF マトリックスを構築する
        self.tfidf_matrix = self.vectorizer.fit_transform(corpus)
        self.is_fitted = True
 
    def search(self, query: str, top_n: int = 20,
               date_filter: int = None, sort_order: str = "relevance") -> list:
        """
        TF-IDF ベースの検索を実行する。
 
        Args:
            query       : 検索クエリ
            top_n       : 返す結果の最大数
            date_filter : 過去何年以内のページだけ対象にするか
                          None=制限なし / 1=1年以内 / 3=3年以内 / 5=5年以内
            sort_order  : 並び順
                          "relevance"=関連度順 / "newest"=新しい順 / "oldest"=古い順
 
        Returns:
            スコア付きの検索結果リスト
        """
        if not self.is_fitted or not query.strip():
            return []
 
        # クエリをベクトル化してコサイン類似度を計算する
        query_vec = self.vectorizer.transform([query])
        similarities = cosine_similarity(query_vec, self.tfidf_matrix)[0]
 
        # 閾値以上のページだけ結果に含める
        results = []
        for idx, base_score in enumerate(similarities):
            if base_score > 0.01:
                page = self.pages[idx].copy()
 
                # ── 期間フィルタ ──────────────────────────────────
                # date_filter が指定されている場合、期間外のページをスキップする
                if date_filter is not None:
                    crawled_at = page.get("crawled_at", "")
                    if crawled_at:
                        try:
                            crawled = datetime.fromisoformat(
                                crawled_at.replace("Z", "+00:00"))
                            days_old = (datetime.now() - crawled.replace(tzinfo=None)).days
                            if days_old > date_filter * 365:
                                continue  # 期間外はスキップ
                        except Exception:
                            pass
                # ────────────────────────────────────────────────
 
                # 追加スコアリングで最終スコアを計算する
                final_score = self._calculate_final_score(
                    page, base_score, query, sort_order)
 
                # スコアをパーセント表示用に変換する
                page["relevance_score"] = round(float(final_score) * 100, 1)
                page["base_score"] = round(float(base_score) * 100, 1)
                results.append(page)
 
        # スコアの高い順に並べて top_n 件を返す
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return results[:top_n]
 
    def _calculate_final_score(self, page: dict, base_score: float,
                                query: str, sort_order: str = "relevance") -> float:
        """
        複数の要素を組み合わせて最終スコアを計算する（内部メソッド）。
 
        Args:
            page       : ページ情報
            base_score : TF-IDFベーススコア
            query      : 検索クエリ
            sort_order : 並び順（"relevance" / "newest" / "oldest"）
 
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
            score *= 1.3          # キーワード一致：+30%
 
        # 3. 新鮮度ボーナス・並び順による重み付け
        crawled_at = page.get("crawled_at", "")
        if crawled_at:
            try:
                crawled = datetime.fromisoformat(crawled_at.replace("Z", "+00:00"))
                days_old = (datetime.now() - crawled.replace(tzinfo=None)).days
 
                if sort_order == "newest":
                    # 新しいほどスコアを大幅に上げる（5年=1825日で0に近づく）
                    date_boost = max(0, 1 - (days_old / 1825))
                    score = score * 0.3 + date_boost * 0.7  # 日付を70%重視
 
                elif sort_order == "oldest":
                    # 古いほどスコアを大幅に上げる（5年=1825日で1に近づく）
                    date_boost = min(1, days_old / 1825)
                    score = score * 0.3 + date_boost * 0.7  # 日付を70%重視
 
                else:
                    # relevance（関連度順）：90日以内のページは最大+20%
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
 
 
# ── シングルトン管理 ──────────────────────────────────────────
 
_engine = None
 
 
def get_engine() -> SearchEngine:
    """検索エンジンのシングルトンを取得する（初回だけ作成）"""
    global _engine
    if _engine is None:
        _engine = SearchEngine()
    return _engine
 
 
def rebuild_index(pages: list):
    """インデックスを再構築する（新しいページが追加されたときに呼び出す）"""
    engine = get_engine()
    engine.build_index(pages)
