from gpt_client import summarize_text

def get_ai_response(user_query, engine):
    # --- ステップ1: 質問から検索用キーワードを抽出させる ---
    keyword_prompt = f"""
    以下の質問から、データベース検索に最適な重要キーワードを2〜3個抽出し、スペース区切りで出力してください。
    余計な解説は不要です。キーワードのみを出力してください。
    質問: {user_query}
    """
    extracted_keywords = summarize_text(keyword_prompt).strip()
    
    # 抽出されたキーワードで検索（例: "パイソン 自動化 メモ"）
    search_results = engine.search(extracted_keywords, top_n=5)
    
    # --- ステップ2: 検索結果が空の場合の再トライ ---
    if not search_results:
        # もしダメなら元のクエリでもう一度だけ試す
        search_results = engine.search(user_query, top_n=3)

    if not search_results:
        return "申し訳ありません。関連する情報がデータベースに見つかりませんでした。", []

    # --- ステップ3: 回答の生成 (以下、以前のロジックと同じ) ---
    context_parts = []
    refs = []
    for res in search_results:
        context_parts.append(f"--- 参照元: {res['title']} ---\n{res['full_text'][:1000]}")
        refs.append({"title": res['title'], "url": res['url']})
    
    context_text = "\n\n".join(context_parts)
    
    answer_prompt = f"""
    あなたは社内ナレッジの専門家です。以下の【検索結果】に基づき回答してください。
    【検索結果】:
    {context_text}
    
    質問: {user_query}
    """
    answer = summarize_text(answer_prompt)
    return answer, refs