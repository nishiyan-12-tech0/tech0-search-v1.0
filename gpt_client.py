"""
gpt_client.py
-------------------------
OpenAI API を使ってテキスト要約を行うためのユーティリティモジュール。

・.env から OPENAI_API_KEY を読み込む
・デプロイ環境では.streamlit/secrets.toml からAPIキーを取得する
・summarize_text() で任意テキストを指定文字数以内で要約
・例外処理つきで安全に API を呼び出す
"""

from openai import OpenAI
from dotenv import load_dotenv
import os
import streamlit as st

# ==============================
#  初期化
# ==============================

# .env を読み込む
load_dotenv()

# API キー取得
api_key = st.secrets["openai"]["api_key"]

if not api_key:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("環境変数 OPENAI_API_KEY が設定されていません。")


# OpenAI クライアント初期化
client = OpenAI(api_key=api_key)


# ==============================
#  要約関数
# ==============================

def summarize_text(text: str, max_chars: int = 300) -> str:
    """
    テキストを指定文字数以内で要約する。

    Parameters
    ----------
    text : str
        要約対象のテキスト
    max_chars : int, optional
        要約後の最大文字数（デフォルト 300）

    Returns
    -------
    str
        要約結果のテキスト
    """

    if not text or not isinstance(text, str):
        raise ValueError("text には文字列を指定してください。")

    request = (
        f"以下の内容を{max_chars}文字以内で要約してください。\n"
        "・事実のみを整理する\n"
        "・主張と取り組みを分かりやすくまとめる\n"
        "・不要な前置きや注意書きは含めない\n"
        "・文章は自然で読みやすくする\n\n"
        f"{text}"
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": request}],
            temperature=0.3,
            max_tokens=600
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        raise RuntimeError(f"OpenAI API 呼び出し中にエラーが発生しました: {e}")


# ==============================
#  動作テスト（直接実行時のみ）
# ==============================

if __name__ == "__main__":
    sample = "これは要約テスト用の文章です。OpenAI API を使って短くまとめます。"
    print("▼ 要約結果")
    print(summarize_text(sample))

