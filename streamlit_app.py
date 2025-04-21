import streamlit as st
import requests
import pandas as pd
import openai
import re

# OpenAI APIキーを Streamlit Cloud の secrets から取得
client = openai.OpenAI(api_key=st.secrets["openai_api_key"])

# 翻訳関数（ChatGPTを使って日本語→英語）
def translate_to_english(japanese_text):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "あなたは優秀な医療翻訳者です。"},
            {"role": "user", "content": f"以下の医学用語を英語に翻訳してください：{japanese_text}"}
        ]
    )
    return response.choices[0].message.content.strip()

# 英訳からシンプルな英語キーワードを抽出（最初に出現する英単語だけ使う）
def extract_english_phrase(text):
    matches = re.findall(r'[A-Za-z0-9+\- ]{3,}', text)
    if matches:
        # 一番短くてアルファベットらしい語を選ぶ
        matches = sorted(matches, key=lambda x: (len(x), x))
        return matches[0].strip()
    return text

# ClinicalTrials.gov API 呼び出し
def fetch_trials(condition, other_terms, location):
    url = "https://clinicaltrials.gov/api/v2/studies"
    params = {
        "query.cond": condition,
        "query.term": other_terms,
        "query.locn": location,
        "filter.overallStatus": "RECRUITING"
    }
    r = requests.get(url, params=params)
    if r.status_code != 200:
        st.error(f"APIエラーが発生しました（ステータスコード: {r.status_code}）")
        st.write("実際のリクエストURL:", r.url)
        st.stop()
    return r.json()

# Streamlit UI
st.title("ClinicalTrials.gov 日本語検索アプリ")

jp_condition = st.text_input("疾患名（例：肺がん）", "肺がん")
jp_other_terms = st.text_input("その他のキーワード（例：ROS1）", "ROS1")
jp_location = st.text_input("実施場所（例：日本）", "日本")

if st.button("検索"):
    # 翻訳
    condition_en_raw = translate_to_english(jp_condition)
    other_terms_en_raw = translate_to_english(jp_other_terms)
    location_en_raw = translate_to_english(jp_location)

    # 英語のキーワードだけ抽出
    condition_en = extract_english_phrase(condition_en_raw)
    other_terms_en = extract_english_phrase(other_terms_en_raw)
    location_en = extract_english_phrase(location_en_raw)

    # 翻訳結果表示
    st.subheader("翻訳結果")
    st.write(f"Condition: {condition_en_raw} → `{condition_en}`")
    st.write(f"Other Terms: {other_terms_en_raw} → `{other_terms_en}`")
    st.write(f"Location: {location_en_raw} → `{location_en}`")

    # ClinicalTrials.gov API検索
    data = fetch_trials(condition_en, other_terms_en, location_en)

    # 検索結果の整形
    studies = data.get("studies", [])
    if not studies:
        st.warning("該当する試験は見つかりませんでした。")
    else:
        results = []
        for study in studies:
            results.append({
                "試験ID": study.get("protocolSection", {}).get("identificationModule", {}).get("nctId", ""),
                "試験名": study.get("protocolSection", {}).get("identificationModule", {}).get("officialTitle", ""),
                "ステータス": study.get("protocolSection", {}).get("statusModule", {}).get("overallStatus", ""),
                "開始日": study.get("protocolSection", {}).get("statusModule", {}).get("startDateStruct", {}).get("startDate", ""),
                "場所": study.get("protocolSection", {}).get("locationsModule", {}).get("locations", [{}])[0].get("locationFacility", ""),
                "リンク": f'https://clinicaltrials.gov/study/{study.get("protocolSection", {}).get("identificationModule", {}).get("nctId", "")}'
            })

        df = pd.DataFrame(results)
        st.subheader("検索結果")
        st.dataframe(df)

        # CSV ダウンロードボタン
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("CSVをダウンロード", data=csv, file_name="clinical_trials.csv", mime="text/csv")
