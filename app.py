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
            # 1. 最新の全ページを取得してインデックスを再作成
            new_pages = get_all_pages()
            rebuild_index(new_pages)
            
            # 2. Streamlitのキャッシュをクリアして最新状態を反映させる
            st.cache_resource.clear()
            
            # 3. 完了メッセージを表示
            st.success("✅ インデックスの更新が完了しました！")
        
            # 4. 画面をリロードして最新の engine を取得し直す
            time.sleep(1)
            st.rerun()

# ── タブ ──────────────────────────────────────────────────────
tab_search, tab_chat, tab_crawl, tab_list = st.tabs(
    ["🔍 検索", "💭チャット", "🤖 クローラー", "📋 一覧"]
)

# ── 検索タブ ───────────────────────────────────────────────────
with tab_search:
    st.subheader("キーワードで検索")

    col_search, col_options = st.columns([3, 1])
    with col_search:
        query = st.text_input("🔍 キーワードを入力", placeholder="例: DX, IoT, 製造業",
                              label_visibility="collapsed")
    with col_options:
        top_n = st.selectbox("表示件数", [10, 20, 50], index=0)

    if query:
        results = engine.search(query, top_n=top_n)
        log_search(query, len(results))    # 検索するたびに自動記録（Step7で実装予定）

        st.markdown(f"**📊 検索結果：{len(results)} 件**（TF-IDFスコア順）")
        st.divider()

        if results:
            for i, page in enumerate(results, 1):
                with st.container():
                    col_rank, col_title, col_score = st.columns([0.5, 4, 1])
                    with col_rank:
                        # 上位3件にはメダルを表示する
                        medal = ["🥇", "🥈", "🥉"][i - 1] if i <= 3 else str(i)
                        st.markdown(f"### {medal}")
                    with col_title:
                        st.markdown(f"### {page['title']}")
                    with col_score:
                        # relevance_score（最終スコア）と base_score（TF-IDFのみ）を両方表示
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

# ── チャットタブ ─────────────────────────────────────────────
with tab_chat:
    st.subheader("💭 AI アシスタント")
    
    # 1. 【最優先】まず「messages」がセッション内にあるか確認し、なければ作る
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # 2. 履歴クリアボタン
    if st.button("🗑️ 履歴をクリア", key="clear_chat"):
        st.session_state.messages = []
        st.rerun()

    # 3. 履歴の表示（ここで st.session_state.messages を使う）
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # 4. 入力欄（これが自動で最下部に固定される）
    if prompt := st.chat_input("質問を入力してください（例: 製造業のDX事例は？）"):
        # ユーザー入力を表示＆保存
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # AIの回答生成ロジック
        with st.chat_message("assistant"):
            with st.spinner("ナレッジベースを検索中..."):
                from chat import get_ai_response # chat.pyからインポート
                answer, refs = get_ai_response(prompt, engine)
                
                full_response = answer
                if refs:
                    full_response += "\n\n---\n**📚 参照元:**\n"
                    for ref in refs:
                        full_response += f"- [{ref['title']}]({ref['url']})\n"
                
                st.markdown(full_response)
        
        # 回答を履歴に保存して再描画
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
                msg = f"🔗 {url_count}/{urls_count}件のURLを処理中"

                st.session_state.crawl_results = []
                progress_bar = st.progress(0, text = msg)
                

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
                    msg = f"🔗 {url_count}/{urls_count}件のURLを処理中"
                    progress_bar.progress((url_count)/urls_count,text=msg)

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
