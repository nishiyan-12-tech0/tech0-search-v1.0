"""
app.py — Tech0 Search v1.0（完成版）
Streamlit アプリ本体。検索・クローラー・一覧の3タブ構成。
"""

import re
import streamlit as st
from database import init_db, get_all_pages, insert_page, log_search
from ranking import get_engine, rebuild_index
from crawler import crawl_url
import time
from gpt_client import summarize_text
from chat import get_ai_response

# アプリ起動時に DB を初期化する（テーブルが未作成なら作る）
init_db()

st.set_page_config(
    page_title="Tech0 Search v1.0",
    page_icon="🔍",
    layout="wide"
)

# ── キャッシュ付きインデックス構築 ─────────────────────────────
@st.cache_resource
def load_and_index():
    """全ページを DB から読み込み TF-IDF インデックスを構築する。
    @st.cache_resource により、アプリ起動中は一度だけ実行される。"""
    pages = get_all_pages()
    if pages:
        rebuild_index(pages)
    return pages

pages = load_and_index()
engine = get_engine()

# ── ヘッダー ──────────────────────────────────────────────────
st.title("🔍 Tech0 Search v1.0")
st.caption("PROJECT ZERO — 社内ナレッジ検索エンジン【TF-IDFランキング搭載】")

with st.sidebar:
    st.header("DB の状態")
    st.metric("登録ページ数", f"{len(pages)} 件")
    if st.button("🔄 インデックスを更新"):
        with st.spinner("インデックスを再構築中..."):
            new_pages = get_all_pages()
            rebuild_index(new_pages)
            st.cache_resource.clear()
            st.success("✅ インデックスの更新が完了しました！")
            time.sleep(1)
            st.rerun()

# ── タブ ──────────────────────────────────────────────────────
tab_search, tab_chat, tab_crawl, tab_list = st.tabs(
    ["🔍 検索", "💭チャット", "🤖 クローラー", "📋 一覧"]
)

# ── 検索タブ ───────────────────────────────────────────────────
with tab_search:
    st.subheader("キーワードで検索")

    # ── 1行目：検索バー ────────────────────────────────────────
    query = st.text_input(
        "🔍 キーワードを入力",
        placeholder="例: DX, IoT, 製造業",
        label_visibility="collapsed"
    )

    # ── 2行目：検索条件 + 検索ボタン ───────────────────────────
    col_n, col_date, col_sort, col_btn = st.columns([1, 1, 1, 1])

    with col_n:
        top_n = st.selectbox("表示件数", [10, 20, 50], index=0)

    with col_date:
        date_label = st.selectbox("期間", [
            "制限なし",
            "1年以内",
            "3年以内",
            "5年以内",
        ])

    with col_sort:
        sort_label = st.selectbox("並び順", [
            "関連度順",
            "新しい順",
            "古い順",
        ])

    with col_btn:
        st.write("")  # ラベル分の余白を合わせる
        search_btn = st.button("🔍 検索", type="primary", use_container_width=True)

    # ── 選択肢を ranking.py が受け取れる値に変換する ──────────
    date_map = {
        "制限なし": None,
        "1年以内": 1,
        "3年以内": 3,
        "5年以内": 5,
    }
    sort_map = {
        "関連度順": "relevance",
        "新しい順": "newest",
        "古い順":   "oldest",
    }

    date_filter = date_map[date_label]
    sort_order  = sort_map[sort_label]

    # ── 検索実行（検索ボタンを押したとき） ────────────────────
    if search_btn and query:
        results = engine.search(
            query,
            top_n=top_n,
            date_filter=date_filter,
            sort_order=sort_order,
        )
        st.session_state.search_results = results  # 結果を保存
        st.session_state.search_info = f"**📊 検索結果：{len(results)} 件**（{sort_label} / {date_label}）"
        log_search(query, len(results))
    elif search_btn and not query:
        st.warning("キーワードを入力してください")

# --- 結果表示部分（ここを独立させる） ---
if "search_results" in st.session_state:
    # 状態から結果を取り出す
    results = st.session_state.search_results
    st.markdown(st.session_state.search_info)        
    st.divider()

    if results:
            for i, page in enumerate(results, 1):
                with st.container():
                    col_rank, col_title, col_score = st.columns([0.5, 4, 1])
                    with col_rank:
                        medal = ["🥇", "🥈", "🥉"][i - 1] if i <= 3 else str(i)
                        st.markdown(f"### {medal}")
                    with col_title:
                        st.markdown(f"### {page['title']}")
                    with col_score:
                        st.metric("スコア", f"{page['relevance_score']}",
                                  delta=f"基準: {page['base_score']}")

                    desc = page.get("description", "")
                    if desc:
                        st.markdown(f"*{desc[:200]}{'...' if len(desc) > 200 else ''}*")

                    kw = page.get("keywords", "") or ""
                    if kw:
                        kw_list = [k.strip() for k in kw.split(",") if k.strip()][:5]
                        tags = " ".join([f"`{k}`" for k in kw_list])
                        st.markdown(f"🏷️ {tags}")

                    col1, col2, col3, col4 = st.columns(4)
                    with col1: st.caption(f"👤 {page.get('author', '不明') or '不明'}")
                    with col2: st.caption(f"📊 {page.get('word_count', 0)} 語")
                    with col3: st.caption(f"📁 {page.get('category', '未分類') or '未分類'}")
                    with col4: st.caption(f"📅 {(page.get('crawled_at', '') or '')[:10]}")

                    st.markdown(f"🔗 [{page['url']}]({page['url']})")

                    if st.button(f"このページを要約する", key=f"search_{page['id']}"):
                        with st.spinner("要約中..."):
                            text = f"{page.get('title', '')}\n\n{page.get('full_text', '')}"
                            summary = summarize_text(text)
                        st.success("要約結果")
                        st.write(summary)

                    st.divider()
    else:
            st.info("該当するページが見つかりませんでした")

elif search_btn and not query:
        st.warning("キーワードを入力してください")

# ── チャットタブ ─────────────────────────────────────────────
with tab_chat:
    st.subheader("💭 AI アシスタント")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    if st.button("🗑️ 履歴をクリア", key="clear_chat"):
        st.session_state.messages = []
        st.rerun()

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("質問を入力してください（例: 製造業のDX事例は？）"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("ナレッジベースを検索中..."):
                answer, refs = get_ai_response(prompt, engine)
                full_response = answer
                if refs:
                    full_response += "\n\n---\n**📚 参照元:**\n"
                    for ref in refs:
                        full_response += f"- [{ref['title']}]({ref['url']})\n"
                st.markdown(full_response)

        st.session_state.messages.append({"role": "assistant", "content": full_response})
        st.rerun()

# ── クローラータブ ─────────────────────────────────────────────
if "crawl_results" not in st.session_state:
    st.session_state.crawl_results = []

with tab_crawl:
    st.subheader("🤖 自動クローラー")
    st.caption("URLを入力してクロールし、インデックスに登録する")

    crawl_url_input = st.text_area(
        "クロール対象URL",
        placeholder="URLを改行またはスペース区切りで入力してください",
        height=150
    )

    if st.button("🤖 クロール実行", type="primary"):
        if crawl_url_input:
            raw_parts = re.split(r'[\s]+', crawl_url_input.strip())
            urls = [p for p in raw_parts if p.startswith(("http://", "https://"))]

            if not urls:
                st.error("有効なURLが見つかりませんでした")
            else:
                urls_count = len(urls)
                url_count = 0
                st.write(f"🔗 {urls_count}件のURLを処理します")
                st.session_state.crawl_results = []
                progress_bar = st.progress(0, text=f"🔗 0/{urls_count}件のURLを処理中")

                for url in urls:
                    with st.spinner(f"クロール中: {url}"):
                        result = crawl_url(url)

                    if result and result.get('crawl_status') == 'success':
                        st.success(f"✅ 成功: {url}")
                        col1, col2 = st.columns(2)
                        with col1:
                            title = result.get('title', '')
                            st.metric("📄 タイトル", (title[:30] + "...") if len(title) > 30 else title)
                        with col2:
                            st.metric("📊 文字数", f"{result.get('word_count', 0)}語")
                        st.session_state.crawl_results.append(result)
                    else:
                        st.error(f"❌ 失敗: {url}")

                    url_count += 1
                    progress_bar.progress(url_count / urls_count,
                                          text=f"🔗 {url_count}/{urls_count}件のURLを処理中")

    if st.session_state.crawl_results:
        st.info(f"{len(st.session_state.crawl_results)}件のクロール結果を登録できます。")

        if st.button("💾 全てインデックスに登録"):
            total = len(st.session_state.crawl_results)
            progress_text = st.empty()
            progress_bar = st.progress(0)

            for i, r in enumerate(st.session_state.crawl_results, start=1):
                progress_text.write(f"📥 {i} / {total} 件登録中...")
                insert_page(r)
                progress_bar.progress(i / total)

            progress_text.write(f"✅ {total} / {total} 件 登録完了！")
            st.success(f"{total}件 登録完了！")
            st.session_state.crawl_results = []
            st.cache_resource.clear()
            time.sleep(10)
            st.rerun()

# ── 一覧タブ ───────────────────────────────────────────────────
with tab_list:
    st.subheader(f"📋 登録済みページ一覧（{len(pages)} 件）")
    if not pages:
        st.info("登録されているページがありません。クローラータブからページを追加してください。")
    else:
        for page in pages:
            with st.expander(f"📄 {page['title']}"):
                st.markdown(f"**URL：** {page['url']}")
                st.markdown(f"**説明：** {page.get('description', '（なし）') or '（なし）'}")
                col1, col2, col3 = st.columns(3)
                with col1: st.caption(f"語数：{page.get('word_count', 0)}")
                with col2: st.caption(f"作成者：{page.get('author', '不明') or '不明'}")
                with col3: st.caption(f"カテゴリ：{page.get('category', '未分類') or '未分類'}")

                if st.button(f"このページを要約する", key=f"list_{page['id']}"):
                    with st.spinner("要約中..."):
                        text = f"{page.get('title', '')}\n\n{page.get('full_text', '')}"
                        summary = summarize_text(text)
                        st.success("要約結果")
                        st.write(summary)

st.divider()
st.caption("© 2025 PROJECT ZERO — Tech0 Search v1.0 | Powered by TF-IDF")
